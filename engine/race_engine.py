import math
import random
from typing import List, Dict, Any, Optional

from engine.events import SCHEMA_VERSION


# Caution (neutralizasyon) şiddet sıralaması
_CAUTION_RANK = {None: 0, "VSC": 1, "SC": 2, "RED": 3}

# Mekanik DNF sebep çeşitliliği (anlatı/rapor zenginliği; mekanik etki aynı)
_MECH_FAILURES = ["motor", "şanzıman", "hidrolik", "fren", "elektrik", "soğutma"]


class LapRaceEngine:
    """
    Tur tur (lap-by-lap) yarış motoru.

    RNG enjeksiyonu: tüm zar atışları self.rng üzerinden gider. simulate_race'e
    seed verilirse yarış birebir tekrarlanabilir (replay = seed + aynı girdiler).
    """

    def __init__(self, settings, rng: Optional[random.Random] = None):
        self.settings = settings
        self.rng = rng or random.Random()

    # ---------------------------------------------------------------- temel hesaplar

    def _track_overtaking_difficulty(self, track) -> float:
        explicit = getattr(track, "overtaking_difficulty", None)
        if explicit is not None:
            return explicit
        raw = 0.25 + track.req_grip * 0.7 + track.req_driver_skill * 0.3
        return max(0.1, min(0.9, raw))

    def _base_lap_time(self, base_power: float, track) -> float:
        s = self.settings
        track_base_time = getattr(track, "base_lap_time", None) or s.BASE_LAP_TIME
        
        diff = base_power - s.PACE_REFERENCE
        if diff > 0:
            diff = diff ** 0.8 
        elif diff < 0:
            diff = -((-diff) ** 0.8)
            
        multiplier = 1 - (diff * s.PACE_SENSITIVITY)
        return track_base_time * multiplier

    def _lap_noise_sigma(self, consistency: float) -> float:
        return self.settings.LAP_NOISE_BASE * (1 + (100 - consistency) / 100.0)

    def _per_lap_prob(self, risk_per_1000: float, num_laps: int) -> float:
        race_p = min(0.95, max(0.0, risk_per_1000 / 1000.0))
        return 1 - (1 - race_p) ** (1.0 / num_laps)

    def _track_tyre_severity(self, track) -> float:
        # Açık değer verilmişse onu kullan (sokak pistleri grip istese de lastiği
        # az yer — Monako gerçekte 1-stop pistidir; formül bunu bilemez).
        explicit = getattr(track, "tyre_severity", None)
        if explicit is not None:
            return explicit
        return 0.7 + track.req_grip * 0.9

    # ---------------------------------------------------------------- hava tahmini

    def make_forecast(self, track, num_laps: int) -> Dict[str, Any]:
        s = self.settings
        rain_prob = min(0.92, track.weather_volatility * s.RAIN_EVENT_SCALE)
        exp_start = self.rng.randint(max(1, num_laps // 5), max(2, int(num_laps * 0.7)))
        exp_intensity = self.rng.uniform(0.40, 0.95)
        exp_duration = self.rng.randint(5, max(6, num_laps // 2))
        label = (f"%{rain_prob * 100:.0f} yağış olasılığı, ~{exp_start}. turda, "
                 f"şiddet {exp_intensity:.2f}, ~{exp_duration} tur sürmesi bekleniyor"
                 if rain_prob > 0.05 else "kuru, yağış beklenmiyor")
        return {"rain_prob": rain_prob, "exp_start": exp_start, "exp_intensity": exp_intensity,
                "exp_duration": exp_duration, "confidence": s.FORECAST_CONFIDENCE, "label": label}

    def _realize_weather(self, forecast: Dict[str, Any], num_laps: int):
        wet = [0.0] * (num_laps + 2)
        if self.rng.random() >= forecast["rain_prob"]:
            return wet, 0.0, False
        conf = forecast["confidence"]
        start = int(round(forecast["exp_start"] + self.rng.gauss(0, (1 - conf) * 8)))
        start = max(1, min(num_laps - 2, start))
        peak = max(0.30, min(1.0, forecast["exp_intensity"] * (1 + self.rng.gauss(0, (1 - conf) * 0.4))))
        dur = max(3, int(round(forecast["exp_duration"] + self.rng.gauss(0, (1 - conf) * 6))))
        ramp_up = max(3, min(10, int(round(9 - peak * 5 + self.rng.gauss(0, 1)))))
        ramp_down = max(4, min(12, int(round(4 + peak * 7 + self.rng.gauss(0, 1)))))
        for i in range(num_laps + 2):
            if i < start:
                w = 0.0
            elif i < start + ramp_up:
                progress = (i - start + 1) / ramp_up
                w = peak * (progress ** 1.35)
            elif i < start + ramp_up + dur:
                w = peak
            else:
                progress = (i - (start + ramp_up + dur)) / max(1, ramp_down)
                w = peak * (max(0.0, 1 - progress) ** 1.15)
            wet[i] = max(0.0, min(1.0, w))
        return wet, round(max(wet), 2), True

    @staticmethod
    def _weather_label(wetness: float) -> str:
        if wetness < 0.05: return "kuru"
        if wetness < 0.22: return "nemli"
        if wetness < 0.62: return "ıslak"
        return "sağanak"

    @staticmethod
    def _band_rank(band: str) -> int:
        return {"kuru": 0, "nemli": 1, "ıslak": 2, "sağanak": 3}.get(band, 0)

    # ---------------------------------------------------------------- lastik / ıslaklık

    def _compound_category(self, compound: str) -> str:
        c = self.settings.TYRE_COMPOUNDS[compound]
        if c["type"] == "dry": return "dry"
        return "wet" if compound == "wet" else "inter"

    def _desired_category(self, wetness: float, wet_bias: float = 0.0,
                          current_compound: Optional[str] = None) -> str:
        s = self.settings
        current = self._compound_category(current_compound) if current_compound else None
        dry_to_inter = s.DRY_TYRE_WET_THRESHOLD + wet_bias
        inter_to_dry = s.DRY_TYRE_BACK_THRESHOLD + wet_bias
        inter_to_wet = s.WET_TYRE_THRESHOLD + wet_bias
        wet_to_inter = s.WET_TYRE_BACK_THRESHOLD + wet_bias

        if current == "wet":
            return "wet" if wetness >= wet_to_inter else ("inter" if wetness >= inter_to_dry else "dry")
        if current == "inter":
            if wetness >= inter_to_wet:
                return "wet"
            return "inter" if wetness >= inter_to_dry else "dry"

        if wetness >= inter_to_wet: return "wet"
        if wetness >= dry_to_inter: return "inter"
        return "dry"

    def _desired_compound(self, planned_dry: str, wetness: float, wet_bias: float,
                          current_compound: Optional[str] = None) -> str:
        cat = self._desired_category(wetness, wet_bias, current_compound)
        if cat == "wet": return "wet"
        if cat == "inter": return "inter"
        return planned_dry

    def _tyre_wrongness(self, compound: str, wetness: float) -> int:
        order = {"dry": 0, "inter": 1, "wet": 2}
        return abs(order[self._compound_category(compound)] - order[self._desired_category(wetness)])

    def _tyre_condition(self, compound: str, wetness: float):
        s = self.settings
        comp = s.TYRE_COMPOUNDS[compound]
        mismatch = abs(wetness - comp["ideal_wet"])
        pace_pen = s.WET_MISMATCH_PACE * mismatch
        wear_mult = 1.0 + s.WET_WEAR_COEFF * mismatch
        if comp["type"] == "dry" and wetness > 0.5:
            pace_pen += s.SLICK_FLOOD_PEN * (wetness - 0.5)
        return pace_pen, wear_mult

    def _crash_multiplier(self, compound: str, wetness: float) -> float:
        s = self.settings
        wrong = self._tyre_wrongness(compound, wetness)
        return (1.0 + s.WET_CRASH_COEFF * wetness) * (s.WRONG_TYRE_CRASH_STEP ** wrong)

    # ---------------------------------------------------------------- olay/kaza çözümü

    def _apply_crash_outcome(self, st, lap, log, context: str) -> str:
        s = self.settings
        roll = self.rng.random()
        if roll < s.CRASH_RETIRE_PROB:
            st["running"] = False
            st["dnf_lap"] = lap
            st["dnf_cause"] = "crash"
            log(lap, "DNF", f"DNF (KAZA, {context}): {st['driver_id']}",
                driver=st["driver_id"], cause="crash", context=context)
            return "retire"
        if roll < s.CRASH_RETIRE_PROB + s.CRASH_DAMAGE_PROB:
            st["pending_repair"] = True
            st["pace_penalty"] *= (1 + s.DAMAGE_PACE_PENALTY)
            st["repairs"] += 1
            log(lap, "DAMAGE", f"Hasarlı ({context}): {st['driver_id']} pite girip onarıyor, devam",
                driver=st["driver_id"], context=context)
            return "damage"
        st["incident_time_loss"] += s.MINOR_TIME_LOSS
        log(lap, "SPIN", f"Spin/çıkış ({context}): {st['driver_id']} zaman kaybetti",
            driver=st["driver_id"], context=context, time_loss=s.MINOR_TIME_LOSS)
        return "minor"

    def _roll_caution(self, severity: str, wetness: float):
        s = self.settings
        if severity == "retire":
            r = self.rng.random()
            sc_p = s.SC_FROM_CRASH_PROB + s.SC_WET_BONUS * wetness
            if r < s.RED_FLAG_PROB: return "RED"
            if r < s.RED_FLAG_PROB + sc_p: return "SC"
            if r < s.RED_FLAG_PROB + sc_p + s.VSC_FROM_CRASH_PROB: return "VSC"
            return None
        if severity == "damage":
            return "VSC" if self.rng.random() < s.VSC_FROM_DAMAGE_PROB else None
        return None

    def _resolve_mech(self, st, lap, num_laps, log):
        s = self.settings
        detail = self.rng.choice(_MECH_FAILURES)
        if lap >= num_laps * s.LIMP_WINDOW and self.rng.random() < s.LATE_LIMP_PROB:
            st["pace_penalty"] *= (1 + s.LIMP_PACE_PENALTY)
            log(lap, "LIMP", f"Mekanik sorun ({detail}): {st['driver_id']} topallayarak devam (hız/sıra kaybı)",
                driver=st["driver_id"], detail=detail)
            return None
        if self.rng.random() < s.MECH_RETIRE_PROB:
            st["running"] = False
            st["dnf_lap"] = lap
            st["dnf_cause"] = "mech"
            st["dnf_detail"] = detail
            log(lap, "DNF", f"DNF ({detail} arızası): {st['driver_id']}",
                driver=st["driver_id"], cause="mech", detail=detail)
            return "VSC" if self.rng.random() < s.VSC_FROM_MECH_PROB else None
        st["pending_repair"] = True
        st["pace_penalty"] *= (1 + s.DAMAGE_PACE_PENALTY * 0.5)
        st["repairs"] += 1
        log(lap, "REPAIR", f"Parça değişimi pit'i ({detail}): {st['driver_id']} devam ediyor",
            driver=st["driver_id"], detail=detail)
        return None

    def _bunch_field(self, track_order, anchor_extra: float, gap: float):
        if not track_order:
            return
        ordered = sorted(track_order, key=lambda s: s["cumulative_time"])
        base = ordered[0]["cumulative_time"] + anchor_extra
        for i, st in enumerate(ordered):
            st["cumulative_time"] = base + i * gap

    def _tyre_race_score(self, st) -> float:
        s = self.settings
        comp = s.TYRE_COMPOUNDS[st["current_compound"]]
        # Aşınma etkisi bileşimin kendi eğrisiyle ölçeklenir (medium = 1.0 taban,
        # OVERTAKE_TYRE_STATE_SCALE yeniden ayar gerektirmez). Uçurumu geçen lastik
        # sollamaya karşı ekstra savunmasızdır.
        severity = comp.get("wear_time_coeff", s.WEAR_TIME_COEFF) / s.WEAR_TIME_COEFF
        score = comp["pace"] - st["wear_pct"] * 0.08 * severity
        if st["wear_pct"] > comp.get("cliff", s.WEAR_CLIFF):
            score -= 0.06
        return score

    def _next_plan_switch(self, st, lap, num_laps):
        """Plandaki bir sonraki bileşim değişimini döner: (yeni_bileşim, kaç tur sonra)."""
        cur = st["compound_by_lap"].get(lap, st["current_compound"])
        for L in range(lap + 1, num_laps + 1):
            if st["compound_by_lap"][L] != cur:
                return st["compound_by_lap"][L], L - lap
        return None, None

    def _caution_pit(self, st, lap, num_laps, wetness, log, track, discount, label,
                     severity=1.0) -> float:
        """SC/VSC altında ucuz pit kararı.
        PITWALL açıkken: gerçek EV hesabı — 'mevcut programla devam' ile 'şimdi
        indirimli pit + yeniden planlanmış kalan yarış' kıyaslanır; risk profili
        eşiği + karar zarı uygulanır. Kapalıyken eski guard mantığı (A/B testi)."""
        s = self.settings
        desired = self._desired_compound(
            st["compound_by_lap"].get(lap, st["current_compound"]),
            wetness, st["wet_bias"], st["current_compound"])
        weather_switch = self._compound_category(desired) != self._compound_category(st["current_compound"])
        recently = lap - st["last_pit_lap"] < s.SC_PIT_MIN_GAP_LAPS

        new_comp, ev_note, pitnow_plan, gain_est = None, "", None, None
        if weather_switch:
            new_comp = desired                       # yanlış kategorideki lastik: zorunlu
        elif not s.PITWALL_ENABLED:
            # --- ESKİ GUARD MANTIĞI (PITWALL kapalıyken, kıyas için korunur) ---
            worn = st["wear_pct"] >= s.SC_PIT_WEAR_MIN
            next_comp, laps_to_switch = self._next_plan_switch(st, lap, num_laps)
            upcoming = laps_to_switch is not None and laps_to_switch <= s.SC_PIT_LOOKAHEAD
            if not ((worn or upcoming) and not recently):
                return 0.0
            new_comp = (next_comp if upcoming else (next_comp or st["current_compound"]))
        else:
            # --- PİT DUVARI EV KARARI ---
            if recently or st["wear_pct"] < 0.12 or num_laps - lap < 3:
                return 0.0
            stay_runs = self._schedule_runs(st, lap, num_laps)
            stay_cost = self._tail_cost(stay_runs, st["wear_pct"],
                                        st["tyre_wear_coeff"], severity, track)
            pitnow_plan = self._plan_tail(st, lap, num_laps, severity, track,
                                          switch_now=True, first_pit_discount=discount)
            if pitnow_plan is None:
                return 0.0
            gain = stay_cost - pitnow_plan["cost"]
            # Pozisyon maliyeti: pit altında kuyruğa düşmek, sollaması zor pistte
            # süre-EV'nin görmediği bir bedel (geri geçemezsin). Zorlukla ölçekli.
            gain -= s.PITWALL_SC_POS_COST * self._track_overtaking_difficulty(track)
            profile = s.PITWALL_RISK.get(st.get("risk", "orta"), s.PITWALL_RISK["orta"])
            decide = gain > profile["sc_gain"]
            # Karar zarı YALNIZ marjinal kararlarda atılır (eşiğe yakın iki makul
            # aksiyon arasında) — bariz kararı kimse ters çevirmez ("lastik ölüyor,
            # pit şart" gibi). Adalet ilkesi: kötü zar = ikinci en iyi seçenek,
            # asla saçma seçenek değil.
            marginal = abs(gain - profile["sc_gain"]) <= 6.0
            if marginal and self.rng.random() < profile["err"]:
                decide = not decide
            if not decide:
                if gain > 3.0:   # kaçırılan bariz fırsat da görünür olsun (şeffaflık)
                    log(lap, "PITWALL",
                        f"Pit duvarı ({label}): {st['driver_id']} fırsatı PAS GEÇTİ "
                        f"(tahmini +{gain:.1f}s kazanç vardı)",
                        driver=st["driver_id"], action="pass", reason=label,
                        gain_est=round(gain, 1))
                return 0.0
            new_comp = pitnow_plan["next"]
            ev_note = f" (tahmini net {gain:+.1f}s)"
            gain_est = round(gain, 1)

        base_loss = getattr(track, "pit_loss", None) or s.PIT_LANE_LOSS
        pit_loss = max(0.0, base_loss * discount + self.rng.gauss(0, s.PIT_TIME_SIGMA))
        st["current_compound"] = new_comp
        st["compounds_used"].add(new_comp)
        st["stint_history"].append({"compound": new_comp, "from": lap, "reason": label})
        st["wear_pct"] = 0.0
        st["pits"] += 1
        st["last_pit_lap"] = lap
        st["pending_switch_lap"] = None
        st["loss_pit"] += pit_loss
        # Pit sonrası kalan program: SC piti planı değiştirdi -> kuyruk yeniden yazılır
        if pitnow_plan is not None:
            self._rewrite_tail(st, lap, num_laps, pitnow_plan, switch_now=True)
        extra = {"gain_est": gain_est} if gain_est is not None else {}
        log(lap, "PIT", f"PIT ({label} altında, {new_comp}): {st['driver_id']} "
                        f"ucuz pit fırsatını kullandı{ev_note}",
            driver=st["driver_id"], compound=new_comp, reason=label, **extra)
        return pit_loss

    def _red_flag_free_tyres(self, track_order, lap, wetness, log):
        """
        Kırmızı bayrak kuralı (gerçek F1): yarış durduğunda takımlar bedava
        lastik değiştirebilir. Koşullara uygun bileşim takılır, aşınma sıfırlanır,
        süre kaybı yoktur. (Pit penceresini kaçırmış araçlar için büyük piyango —
        agresif/erken pit kumarının doğal dengeleyicisi.)
        """
        changes = {}
        for st in track_order:
            new_comp = self._desired_compound(
                st["compound_by_lap"][lap], wetness, st["wet_bias"], st["current_compound"])
            changes[st["driver_id"]] = new_comp
            if new_comp != st["current_compound"]:
                st["stint_history"].append(
                    {"compound": new_comp, "from": lap, "reason": "kırmızı"})
            else:   # aynı bileşim, taze set — yine kaydedilir (aşınma sıfırlandı)
                st["stint_history"].append(
                    {"compound": new_comp, "from": lap, "reason": "kırmızı (taze set)"})
            st["current_compound"] = new_comp
            st["compounds_used"].add(new_comp)
            st["wear_pct"] = 0.0
        log(lap, "RED_TYRES", "🔴 Kırmızı bayrak: tüm araçlara bedava taze lastik takıldı",
            changes=changes)

    # ---------------------------------------------------------------- pit duvarı
    # Dinamik yarış içi strateji: yarış öncesi kart bir NİYETTİR; yağmur biter,
    # SC çıkar, kural-2 yaklaşırken pit duvarı kalan yarışı yeniden planlar.
    # Temel veri yapısı PENCERE: aday pit turlarının maliyet eğrisinin dibi +
    # PIT_WINDOW_EPS içindeki aralık. Kumar = pencereyi bilinçli esnetmek
    # (bedeli tur başına bilinen "kanama", PITWALL_MAX_BLEED ile tavanlı).

    def _dry_used(self, st):
        s = self.settings
        return {c for c in st["compounds_used"] if s.TYRE_COMPOUNDS[c]["type"] == "dry"}

    def _wet_used(self, st) -> bool:
        s = self.settings
        return any(s.TYRE_COMPOUNDS[c]["type"] == "wet" for c in st["compounds_used"])

    def _stint_cost(self, comp_name: str, laps: int, w0: float, coeff: float,
                    severity: float, base: float) -> float:
        """Bir stintin göreli süre maliyeti (kapalı form — sweep için O(1)).
        deg = tc*wear lineer bölge + cliff sonrası cc*(wear-cliff); bileşim
        temposu -pace*base. w0 = stinte girerkenki aşınma."""
        if laps <= 0:
            return 0.0
        s = self.settings
        comp = s.TYRE_COMPOUNDS[comp_name]
        r = comp["wear_rate"] * coeff * severity
        tc = comp.get("wear_time_coeff", s.WEAR_TIME_COEFF)
        cc = comp.get("cliff_coeff", s.WEAR_CLIFF_COEFF)
        cliff = comp.get("cliff", s.WEAR_CLIFF)
        L = laps
        cost = -comp["pace"] * base * L
        cost += tc * (L * w0 + r * L * (L + 1) / 2.0)
        end_wear = w0 + r * L
        if end_wear > cliff and r > 0:
            k0 = max(0, math.ceil((cliff - w0) / r))   # cliff'e kadar tur
            m = L - k0
            if m > 0:
                sum_k = (L * (L + 1) - k0 * (k0 + 1)) / 2.0
                cost += cc * (m * (w0 - cliff) + r * sum_k)
        return cost

    def _tail_cost(self, runs, w0: float, coeff: float, severity: float,
                   track, first_pit_discount: float = 1.0) -> float:
        """runs: [(bileşim, tur)] — kalan yarışın göreli maliyeti. İlk run mevcut
        lastikle w0'dan devam eder; sonraki her run pit kaybı + taze lastik."""
        s = self.settings
        base = getattr(track, "base_lap_time", None) or s.BASE_LAP_TIME
        pit_loss = getattr(track, "pit_loss", None) or s.PIT_LANE_LOSS
        total = 0.0
        for i, (c, laps) in enumerate(runs):
            if i > 0:
                total += pit_loss * (first_pit_discount if i == 1 else 1.0)
            total += self._stint_cost(c, laps, w0 if i == 0 else 0.0, coeff, severity, base)
        return total

    def _schedule_runs(self, st, lap: int, num_laps: int):
        """Mevcut compound_by_lap programını [(bileşim, tur)] run listesine çevirir
        (lap..num_laps aralığı; ilk run mevcut bileşimle devam varsayılır)."""
        runs = []
        cur, count = st["current_compound"], 0
        for L in range(lap, num_laps + 1):
            c = st["compound_by_lap"].get(L, cur)
            if c == cur:
                count += 1
            else:
                runs.append((cur, count))
                cur, count = c, 1
        runs.append((cur, count))
        return runs

    def _plan_tail(self, st, lap: int, num_laps: int, severity: float, track,
                   switch_now: bool = False, first_pit_discount: float = 1.0):
        """Kalan yarış (lap..num_laps) için en iyi programı arar.
        switch_now=True: araç ŞİMDİ pit yapacak (SC fırsatı / kuruma) — ilk run
        taze lastikle başlar ve ilk pit indirimi uygulanabilir.
        Döner: {"runs", "cost", "pit_lap", "next", "window", "best_lap"} | None"""
        s = self.settings
        n = num_laps - lap + 1
        if n <= 2:
            return None
        cur = st["current_compound"]
        w0 = st["wear_pct"]
        coeff = st["tyre_wear_coeff"]
        cur_dry = s.TYRE_COMPOUNDS[cur]["type"] == "dry"
        dry = [c for c, d in s.TYRE_COMPOUNDS.items() if d["type"] == "dry"]
        used_dry = self._dry_used(st)
        needs_second = (not self._wet_used(st)) and len(used_dry) <= 1

        def cost_of(runs, disc=1.0):
            return self._tail_cost(runs, 0.0 if switch_now else w0, coeff, severity,
                                   track, first_pit_discount=disc)

        best = None
        sweep = {}   # (pit_lap, next_comp) -> cost  (pencere hesabı için)

        if switch_now:
            # Şimdi pitleniyor: hangi taze bileşim + sonrasında ek stop gerekir mi?
            pit0 = getattr(track, "pit_loss", None) or s.PIT_LANE_LOSS
            for c1 in dry:
                if needs_second and len(used_dry) == 1 and c1 in used_dry and n > 8:
                    pass  # aynı bileşimi takmak kuralı çözmez ama ek stopla çözülebilir
                # tek stint sona kadar
                runs = [(c1, n)]
                rule_ok = (not needs_second) or (c1 not in used_dry) or self._wet_used(st)
                c = pit0 * first_pit_discount + self._tail_cost(
                    [(c1, n)], 0.0, coeff, severity, track)
                if rule_ok and (best is None or c < best["cost"]):
                    best = {"runs": runs, "cost": c, "pit_lap": lap, "next": c1,
                            "window": None, "best_lap": lap}
                # c1 + ikinci stop c2 (kural/cliff gerekirse)
                for c2 in dry:
                    if needs_second and c1 in used_dry and c2 == c1:
                        continue
                    for T in range(lap + 4, num_laps - 2, 2):
                        runs2 = [(c1, T - lap), (c2, num_laps - T + 1)]
                        c = pit0 * first_pit_discount + self._tail_cost(
                            runs2, 0.0, coeff, severity, track)
                        if best is None or c < best["cost"]:
                            best = {"runs": runs2, "cost": c, "pit_lap": lap, "next": c1,
                                    "window": None, "best_lap": lap}
            return best

        # Normal mod: mevcut lastikle devam + ileride 0/1/2 stop
        if cur_dry and not needs_second:
            runs = [(cur, n)]
            c = cost_of(runs)
            best = {"runs": runs, "cost": c, "pit_lap": None, "next": None,
                    "window": None, "best_lap": None}

        if cur_dry:
            for c2 in dry:
                if needs_second and len(used_dry) == 1 and c2 in used_dry:
                    continue
                for T in range(lap + 2, num_laps - 1):
                    runs = [(cur, T - lap), (c2, num_laps - T + 1)]
                    c = cost_of(runs)
                    sweep[(T, c2)] = c
                    if best is None or c < best["cost"]:
                        best = {"runs": runs, "cost": c, "pit_lap": T, "next": c2,
                                "window": None, "best_lap": T}
            # 2-stop (yüksek aşınma/uzun yarış güvencesi): kaba ızgara
            for c2 in dry:
                for c3 in dry:
                    if needs_second and len(used_dry) == 1 and \
                            c2 in used_dry and c3 in used_dry:
                        continue
                    for T in range(lap + 4, num_laps - 8, 4):
                        mid = (num_laps - T) // 2
                        if mid < 4:
                            continue
                        runs = [(cur, T - lap), (c2, mid), (c3, num_laps - T - mid + 1)]
                        c = cost_of(runs)
                        if best is None or c < best["cost"]:
                            best = {"runs": runs, "cost": c, "pit_lap": T, "next": c2,
                                    "window": None, "best_lap": T}

        if best is None:
            return None
        # PENCERE: en iyi planın bileşimi için dip + EPS içindeki pit turları
        if best["pit_lap"] is not None and best["next"] is not None:
            same = [(T, c) for (T, c2), c in sweep.items() if c2 == best["next"]]
            if same:
                in_win = [T for T, c in same if c <= best["cost"] + s.PIT_WINDOW_EPS]
                if in_win:
                    best["window"] = (min(in_win), max(in_win))
        return best

    def _rewrite_tail(self, st, lap: int, num_laps: int, plan, switch_now: bool = False):
        """compound_by_lap'in kalan kısmını yeni programla değiştirir.
        switch_now=False: bu tur mevcut bileşim korunur (pit, plandaki sınırda)."""
        cbl = st["compound_by_lap"]
        L = lap
        for comp, laps in plan["runs"]:
            for _ in range(max(0, laps)):
                if L > num_laps:
                    break
                cbl[L] = comp
                L += 1
        last = plan["runs"][-1][0]
        while L <= num_laps:
            cbl[L] = last
            L += 1

    def _replan(self, st, lap: int, num_laps: int, severity: float, track,
                log, reason: str):
        """Pit duvarı yeniden planlaması: kalan yarışı optimize eder, pencereyi
        hesaplar, risk profiline göre hedef pit turunu yerleştirir ve loglar."""
        s = self.settings
        if not s.PITWALL_ENABLED or not st["running"]:
            return
        # Araç ıslak lastikteyse (kuruma replanı) plan "şimdi kuruya geç" modunda
        # kurulur: ilk run taze kuru bileşim, geçişi hava mantığı (lag'li) yapar.
        on_wet = s.TYRE_COMPOUNDS[st["current_compound"]]["type"] == "wet"
        plan = self._plan_tail(st, lap, num_laps, severity, track, switch_now=on_wet)
        if plan is None:
            return
        profile = s.PITWALL_RISK.get(st.get("risk", "orta"), s.PITWALL_RISK["orta"])
        # Risk yerleştirmesi: pencere dibinden sonra fırsat bekleme (stretch) —
        # kanama tavanı aşılmadan; ayrıca küçük zar gürültüsü (±1 tur).
        if plan["pit_lap"] is not None and plan["window"]:
            lo, hi = plan["window"]
            target = plan["best_lap"] + profile["stretch"]
            if profile["err"] > 0 and self.rng.random() < 0.5:
                target += self.rng.choice([-1, 1])
            target = max(lo, min(target, hi + profile["stretch"], num_laps - 2))
            if target != plan["pit_lap"]:
                first = target - lap
                rest = num_laps - target + 1
                if first >= 1 and rest >= 2:
                    plan["runs"] = [(st["current_compound"], first)] + \
                                   [(c, l) for c, l in plan["runs"][1:]]
                    # son run kalanı kapatsın
                    used = first + sum(l for _, l in plan["runs"][1:-1])
                    lc = plan["runs"][-1][0]
                    plan["runs"][-1] = (lc, max(2, num_laps - lap + 1 - used))
                    plan["pit_lap"] = target
        self._rewrite_tail(st, lap, num_laps, plan)
        if plan["pit_lap"] is not None:
            win_txt = (f", pencere T{plan['window'][0]}-T{plan['window'][1]}"
                       if plan["window"] else "")
            log(lap, "PITWALL",
                f"Pit duvarı ({reason}): {st['driver_id']} -> {plan['next']} "
                f"@T{plan['pit_lap']}{win_txt}",
                driver=st["driver_id"], action="plan", reason=reason,
                pit_lap=plan["pit_lap"], compound=plan["next"], window=plan["window"])
        else:
            log(lap, "PITWALL",
                f"Pit duvarı ({reason}): {st['driver_id']} sona kadar devam",
                driver=st["driver_id"], action="stay", reason=reason)

    def _overtake_success(self, attacker, defender, ot_difficulty, drs_on, extra_bonus=0.0) -> bool:
        s = self.settings
        pilot_diff = (attacker["attack_defense"] - defender["attack_defense"]) / 100.0 * 0.15
        power_diff = (attacker["base_power"] - defender["base_power"]) * 0.012
        # TEMİZ tur farkı: battle/kaza/onarım kayıpları hariç (clean_lap_time).
        # Eski model last_lap_time kullanıyordu; atak yapanın kendi mücadele
        # kayıpları kendi pace'ini kirletiyordu (hücum etmek hücum gücünü düşürüyordu).
        pace_delta = (defender.get("clean_lap_time") or defender.get("last_lap_time", 0.0)) \
                   - (attacker.get("clean_lap_time") or attacker.get("last_lap_time", 0.0))
        # Süperlineer ödül: küçük farklar mütevazı, büyük farklar orantıdan fazla kazandırır
        pace_bonus = pace_delta * s.OVERTAKE_PACE_DELTA_SCALE * (1.0 + abs(pace_delta) * s.OVERTAKE_PACE_DELTA_CURVE)
        pace_bonus = max(-0.10, min(s.OVERTAKE_PACE_BONUS_CAP, pace_bonus))
        tyre_state_diff = self._tyre_race_score(attacker) - self._tyre_race_score(defender)
        tyre_bonus = max(-0.05, min(0.08, tyre_state_diff * s.OVERTAKE_TYRE_STATE_SCALE))

        track_factor = max(0.05, (1 - ot_difficulty) ** 1.7)
        prob = (s.BASE_OVERTAKE_CHANCE + pilot_diff + power_diff + pace_bonus + tyre_bonus) * track_factor

        if drs_on:
            prob += s.DRS_BOOST * track_factor
        prob += extra_bonus

        max_prob = 0.08 + (1 - ot_difficulty) * 0.42
        # Büyük pace farkında tavan gevşer: backmarker çok daha hızlı aracı
        # zor pistte bile sonsuza dek arkasında tutamamalı.
        if pace_bonus > 0:
            max_prob += pace_bonus * s.OVERTAKE_CAP_RELAX
        return self.rng.random() < max(0.003, min(max_prob, prob))

    # ---------------------------------------------------------------- ana döngü

    def roll_race_conditions(self) -> Dict[str, float]:
        """Yarış günü koşullarını üretir. Yarış ÖNCESİ çağrılıp oyuncuya gösterilebilir
        ve simulate_race'e conditions olarak geçirilebilir (strateji seçimine girdi)."""
        s = self.settings
        return {
            "wear_day_mult": self.rng.uniform(1 - s.RACE_DAY_WEAR_VAR, 1 + s.RACE_DAY_WEAR_VAR),
            "ot_day_delta": self.rng.gauss(0, s.RACE_DAY_OT_SIGMA),
        }

    def simulate_race(self, grid_order: List[str], profiles: Dict[str, Dict[str, Any]],
                      track, num_laps: Optional[int] = None,
                      strategies: Optional[Dict[str, Any]] = None,
                      form: Optional[Dict[str, float]] = None,
                      forecast: Optional[Dict[str, Any]] = None,
                      conditions: Optional[Dict[str, float]] = None,
                      seed: Optional[int] = None) -> Dict[str, Any]:
        s = self.settings
        # Determinizm: seed + aynı girdiler (grid/profiles/strategies/forecast/
        # conditions) = birebir aynı yarış. Seed verilmezse üretilip sonuçla
        # birlikte raporlanır; sunucu kaydeder, replay bedavaya gelir.
        if seed is None:
            seed = random.getrandbits(48)
        self.rng = random.Random(seed)
        form = form or {}
        strategies = strategies or {}
        if num_laps is None:
            num_laps = getattr(track, "num_laps", None) or s.DEFAULT_RACE_LAPS

        if forecast is None:
            forecast = self.make_forecast(track, num_laps)
        weather, weather_peak, rained = self._realize_weather(forecast, num_laps)

        # Yarış günü koşulları: pist sıcaklığı/rüzgar gibi etmenler aşınmayı ve geçiş
        # kolaylığını yarıştan yarışa küçük oynatır (anti-meta; ortalama denge korunur).
        # Dışarıdan verilebilir (conditions param) — oyunda yarış öncesi "koşul raporu"
        # olarak oyuncuya gösterilip strateji seçimine girdi olur.
        cond = conditions or self.roll_race_conditions()
        ot_difficulty = max(0.05, min(0.95, self._track_overtaking_difficulty(track) + cond["ot_day_delta"]))
        wear_day_mult = cond["wear_day_mult"]
        tyre_severity = self._track_tyre_severity(track) * wear_day_mult
        events: List[Dict[str, Any]] = []

        def log(lap, etype, msg, **kw):
            ev = {"lap": lap, "type": etype, "msg": msg}
            ev.update(kw)
            events.append(ev)

        states = {}
        for grid_idx, d_id in enumerate(grid_order):
            p = profiles[d_id]
            strat = strategies.get(d_id)
            risk = "orta"
            if isinstance(strat, list):
                plan, wet_bias, reaction_lag = strat, 0.0, s.WEATHER_REACTION_LAG
            elif isinstance(strat, dict):
                plan = strat["plan"]
                wet_bias = strat.get("wet_bias", 0.0)
                reaction_lag = strat.get("reaction_lag", s.WEATHER_REACTION_LAG)
                risk = strat.get("risk", "orta")
            else:
                plan = self._default_strategy(num_laps)
                wet_bias, reaction_lag = 0.0, s.WEATHER_REACTION_LAG
            compound_by_lap = self._expand_plan(plan, num_laps, p.get("tyre_wear_coeff", 1.0))
            states[d_id] = {
                "driver_id": d_id, "team_id": p["team_id"], "grid_pos": grid_idx + 1,
                "base_power": p["base_power"], "consistency": p["consistency"],
                "attack_defense": p["attack_defense"], "tyre_wear_coeff": p["tyre_wear_coeff"],
                "perks": p.get("perks", []), 
                "form": form.get(d_id, 0.0),
                "lap_crash_prob": self._per_lap_prob(p.get("crash_incident_risk", p["crash_risk"]), num_laps),
                "lap_mech_prob": self._per_lap_prob(p.get("mech_risk", 0.0), num_laps),
                "cumulative_time": 0.0, "laps_completed": 0,
                "running": True, "dnf_lap": None, "dnf_cause": None,
                "compound_by_lap": compound_by_lap, "current_compound": compound_by_lap[1],
                "compounds_used": {compound_by_lap[1]},  # iki-bileşim kuralı takibi
                # Stint geçmişi: her bileşim değişimi sebep etiketiyle (plan/hava/
                # SC/VSC/kırmızı) kaydedilir — UI pit raporu / replay / server için
                "stint_history": [{"compound": compound_by_lap[1], "from": 1, "reason": "start"}],
                "wear_pct": 0.0, "pits": 0, "wet_bias": wet_bias, "reaction_lag": reaction_lag,
                "risk": risk, "rule2_planned": False,   # pit duvarı durumu
                "pending_switch_lap": None,
                "pace_penalty": 1.0, "pending_repair": False, "incident_time_loss": 0.0, "repairs": 0,
                "battle_time_loss": 0.0, "pit_loss_this_lap": 0.0,
                "repair_loss_this_lap": 0.0, "incident_loss_this_lap": 0.0,
                "last_lap_time": 0.0, "clean_lap_time": 0.0,
                "dirty_air_cooldown": 0, "last_pit_lap": -99,
                # Yarış sonu analiz için kayıp/kazanç dökümü (saniye, birikimli)
                "loss_pit": 0.0, "loss_repair": 0.0, "loss_incident": 0.0,
                "loss_battle": 0.0, "loss_dirty_air": 0.0, "gain_aero": 0.0,
            }

        track_order = [states[d_id] for d_id in grid_order]
        dnf_states = []
        sc_laps = vsc_laps = 0
        caution_len = 0
        restart_chaos = 0
        prev_leader = track_order[0]["driver_id"] if track_order else None
        prev_band = self._weather_label(weather[1] if len(weather) > 1 else 0.0)

        log(0, "FORECAST", f"Hava tahmini: {forecast['label']}",
            rain_prob=forecast["rain_prob"], exp_start=forecast["exp_start"],
            exp_intensity=forecast["exp_intensity"], exp_duration=forecast["exp_duration"],
            confidence=forecast["confidence"])
        if wear_day_mult > 1.05:
            cond_label = "sıcak pist — yüksek lastik aşınması"
        elif wear_day_mult < 0.95:
            cond_label = "serin pist — düşük lastik aşınması"
        else:
            cond_label = "normal pist sıcaklığı"
        log(0, "CONDITIONS", f"Pist koşulları: {cond_label}",
            wear_mult=round(wear_day_mult, 3), ot_delta=round(cond["ot_day_delta"], 3))
        log(0, "START", f"Yarış başladı — pole: {prev_leader} | başlangıç: {prev_band} | {num_laps} tur",
            driver=prev_leader, band=prev_band, num_laps=num_laps)

        # Perk görünürlüğü: oyuncu hangi perklerin sahada olduğunu görsün
        # (görünmeyen modifier adaletsiz hissettirir, görünen aynı modifier hikâyedir)
        perk_holders = [f"{st['driver_id']} [{', '.join(st['perks'])}]"
                        for st in track_order if st["perks"]]
        if perk_holders:
            log(0, "PERKS", "Sahadaki perkler: " + " | ".join(perk_holders),
                holders={st["driver_id"]: list(st["perks"])
                         for st in track_order if st["perks"]})

        # Pit duvarı: yarış başında tahmini ilk pit pencereleri (bilgi/yayın grafiği).
        # Karta dokunmaz — sadece optimizörün gördüğü pencereyi loglar.
        if s.PITWALL_ENABLED:
            for st in track_order:
                adv = self._plan_tail(st, 1, num_laps, tyre_severity, track)
                if adv and adv.get("window"):
                    lo, hi = adv["window"]
                    log(0, "PITWALL",
                        f"📍 Tahmini ilk pit penceresi: {st['driver_id']} T{lo}-T{hi}",
                        driver=st["driver_id"], action="window", window=(lo, hi))

        # Kalkış (launch) varyansı: ışıklar söndüğünde refleks farkı sıralamayı
        # değiştirebilir. Consistency düşük pilot startı daha sık batırır;
        # Clutch Start perki kötü kalkışı yumuşatır. Yavaş araç iyi kalksa da
        # pace'i yetmiyorsa ilerleyen turlarda pozisyonu doğal olarak geri verir.
        for grid_idx, st in enumerate(track_order):
            # Grid slotları arası fiziksel mesafe: kalkış deltası bununla yarışır,
            # böylece süper kalkış 1-3 sıra kazandırır ama P15'i lider yapamaz.
            st["cumulative_time"] += grid_idx * s.GRID_SLOT_SPACING
            sigma = s.LAUNCH_SIGMA * (1 + (100 - st["consistency"]) / 100.0)
            launch_delta = self.rng.gauss(0, sigma)
            if "Clutch Start" in st["perks"] and launch_delta > 0:
                launch_delta *= 0.4
            launch_delta = max(-s.LAUNCH_MAX, min(s.LAUNCH_MAX, launch_delta))
            st["cumulative_time"] += launch_delta
            if launch_delta <= -1.0:
                log(1, "LAUNCH", f"🚀 Müthiş kalkış: {st['driver_id']} ({-launch_delta:.1f}s kazandı)",
                    driver=st["driver_id"], delta=round(launch_delta, 2))
            elif launch_delta >= 1.0:
                log(1, "LAUNCH", f"🐌 Kötü kalkış: {st['driver_id']} ({launch_delta:.1f}s kaybetti)",
                    driver=st["driver_id"], delta=round(launch_delta, 2))
        track_order.sort(key=lambda x: x["cumulative_time"])

        # Tur tur pozisyon geçmişi (analiz + ileride replay/sunum katmanı için).
        # index 0 = kalkış sonrası diziliş, index L = L. tur sonu diziliş.
        lap_positions = [[st["driver_id"] for st in track_order]]

        track_base_time = getattr(track, "base_lap_time", None) or s.BASE_LAP_TIME

        for lap in range(1, num_laps + 1):
            wetness = weather[lap]
            band = self._weather_label(wetness)
            if band != prev_band:
                worsening = self._band_rank(band) > self._band_rank(prev_band)
                verb = "kötüleşiyor" if worsening else "düzeliyor"
                log(lap, "WEATHER", f"Hava: {prev_band} -> {band} ({verb}, ıslaklık {wetness:.2f})",
                    wetness=round(wetness, 3), band=band, prev_band=prev_band,
                    trend="worsening" if worsening else "improving")
                prev_band = band

            # Pit duvarı — KURUMA TETİĞİ: pist kuruyunca eski kuru plan bayattır
            # (yağmur pitleri programı kaydırdı). Kalan yarış herkes için yeniden
            # planlanır; aksi halde araçlar bayat plana itaat edip anlamsız geç
            # stoplar atıyordu ("stratejiye bağlı kalacağım diye patlama").
            if (s.PITWALL_ENABLED and lap > 1
                    and weather[lap - 1] >= 0.12 > wetness):
                for st in track_order:
                    self._replan(st, lap, num_laps, tyre_severity, track,
                                 log, "pist kuruyor")

            under_caution = sc_laps > 0 or vsc_laps > 0
            req_caution, req_who = None, None

            def request(kind, who):
                nonlocal req_caution, req_who
                if _CAUTION_RANK[kind] > _CAUTION_RANK[req_caution]:
                    req_caution, req_who = kind, who

            # 1) Olaylar
            if not under_caution:
                chaos = s.START_INCIDENT_MULT if lap == 1 else (s.RESTART_INCIDENT_MULT if restart_chaos > 0 else 1.0)
                survivors = []
                for st in track_order:
                    p_crash = st["lap_crash_prob"] * self._crash_multiplier(st["current_compound"], wetness) * chaos
                    p_mech = st["lap_mech_prob"]
                    roll = self.rng.random()
                    if roll < p_crash:
                        sev = self._apply_crash_outcome(st, lap, log, "tek araç")
                        request(self._roll_caution(sev, wetness), st["driver_id"])
                    elif roll < p_crash + p_mech:
                        request(self._resolve_mech(st, lap, num_laps, log), st["driver_id"])
                    if st["running"]:
                        survivors.append(st)
                    else:
                        dnf_states.append(st)
                track_order = survivors

            if req_caution and not under_caution:
                if req_caution == "RED":
                    self._bunch_field(track_order, 0.0, 0.0)
                    self._red_flag_free_tyres(track_order, lap, wetness, log)
                    log(lap, "RED_FLAG", f"🔴 KIRMIZI BAYRAK ({req_who}) — yarış durdu, restart", driver=req_who)
                    if s.PITWALL_ENABLED and wetness < 0.12:
                        for st2 in track_order:   # bedava lastik programları değiştirdi
                            self._replan(st2, lap, num_laps, tyre_severity, track,
                                         log, "kırmızı bayrak")
                    sc_laps, caution_len = 1, 1
                elif req_caution == "SC":
                    self._bunch_field(track_order, s.SC_INLAP_PENALTY, s.SC_GAP)
                    sc_laps = self.rng.randint(s.SC_LAPS_MIN, s.SC_LAPS_MAX)
                    caution_len = sc_laps
                    log(lap, "SC", f"🟡 GÜVENLİK ARACI ({req_who}) — saha toplandı, {sc_laps} tur",
                        driver=req_who, laps=sc_laps)
                else:
                    vsc_laps = self.rng.randint(s.VSC_LAPS_MIN, s.VSC_LAPS_MAX)
                    caution_len = vsc_laps
                    log(lap, "VSC", f"🟡 VSC ({req_who}) — {vsc_laps} tur", driver=req_who, laps=vsc_laps)
                under_caution = True

            # 2) Tur süreleri
            if sc_laps > 0:
                # SC: herkes aynı SC temposunda -> geçiş yok, aralıklar korunur.
                # Ucuz pit penceresi açık: pitlenen araç kuyruğun gerisine düşer
                # (pit kaybı cumulative_time'a eklenince SC dizilişinde geri kayar).
                sc_time = track_base_time * s.SC_SPEED_MULT
                for st in track_order:
                    pit_loss = self._caution_pit(st, lap, num_laps, wetness, log, track,
                                                 s.SC_PIT_DISCOUNT, "SC", tyre_severity)
                    st["cumulative_time"] += sc_time + pit_loss
                    st["wear_pct"] += s.TYRE_COMPOUNDS[st["current_compound"]]["wear_rate"] * st["tyre_wear_coeff"] * tyre_severity * 0.2
                    st["laps_completed"] = lap
            elif vsc_laps > 0:
                # VSC: tüm araçlar AYNI yavaş turu döner -> aralıklar donar, geçiş olmaz.
                # (Eski hali araç bazlı hızla yavaşlatıyordu; hızlı araç VSC altında
                # zaman kazanıp sıralama değiştirebiliyordu — gerçekte yasak.)
                vsc_time = track_base_time * s.VSC_SLOWDOWN
                for st in track_order:
                    pit_loss = self._caution_pit(st, lap, num_laps, wetness, log, track,
                                                 s.VSC_PIT_DISCOUNT, "VSC", tyre_severity)
                    st["cumulative_time"] += vsc_time + pit_loss
                    st["laps_completed"] = lap
            else:
                for i, st in enumerate(track_order):
                    if st["dirty_air_cooldown"] > 0:
                        st["dirty_air_cooldown"] -= 1

                    # Pit duvarı — KURAL-2 CHECKPOINT (yarışın %60'ı): hâlâ tek tip
                    # slick'teyse ikinci bileşimi EN İYİ pencereye şimdiden planla
                    # (son turlarda zorla pit yememek için; N-6 force yedek kalır).
                    if (s.PITWALL_ENABLED and not st["rule2_planned"]
                            and lap == int(num_laps * 0.6) and wetness < 0.15):
                        st["rule2_planned"] = True
                        used_dry = self._dry_used(st)
                        if not self._wet_used(st) and len(used_dry) <= 1:
                            tail_has_other = any(
                                st["compound_by_lap"].get(L) not in used_dry
                                for L in range(lap, num_laps + 1))
                            if not tail_has_other:
                                self._replan(st, lap, num_laps, tyre_severity, track,
                                             log, "iki bileşim kuralı planı")

                    desired = self._desired_compound(
                        st["compound_by_lap"][lap], wetness, st["wet_bias"], st["current_compound"])

                    # GEÇ PLAN PİTİNİ ATLA (dinamik fırsat): plan yarış sonuna doğru
                    # pit diyorsa ama mevcut lastik bitişe kadar uçuruma girmeden
                    # dayanacaksa ve iki-bileşim kuralı zaten sağlanmışsa pite girme —
                    # gerçekte hiçbir takım 8 tur kala sağlam lastiği değiştirmez.
                    if (desired != st["current_compound"]
                            and lap >= num_laps - s.LATE_PIT_SKIP_WINDOW
                            and self._compound_category(desired) ==
                                self._compound_category(st["current_compound"])):
                        cur = s.TYRE_COMPOUNDS[st["current_compound"]]
                        cliff = cur.get("cliff", s.WEAR_CLIFF)
                        proj = st["wear_pct"] + (num_laps - lap) * cur["wear_rate"] * \
                               st["tyre_wear_coeff"] * tyre_severity
                        used_wet = any(s.TYRE_COMPOUNDS[c]["type"] == "wet"
                                       for c in st["compounds_used"])
                        if proj < cliff and (used_wet or len(st["compounds_used"]) > 1):
                            desired = st["current_compound"]

                    # İKİ BİLEŞİM KURALI (gerçek F1): kuru yarış tek tip slick ile
                    # bitirilemez (yarış içinde wet/inter kullanan muaf). Yarış sonuna
                    # yaklaşırken hâlâ tek tipteyse farklı kuru bileşime zorunlu pit.
                    if (not st.get("rule2_done") and lap >= num_laps - 6
                            and wetness < 0.15 and desired == st["current_compound"]):
                        used = st["compounds_used"]
                        used_wet = any(s.TYRE_COMPOUNDS[c]["type"] == "wet" for c in used)
                        if not used_wet and len(used) == 1:
                            only = next(iter(used))
                            desired = "medium" if only != "medium" else "hard"
                            st["rule2_done"] = True
                            log(lap, "PIT_RULE",
                                f"İki bileşim kuralı: {st['driver_id']} farklı slick takmak ZORUNDA",
                                driver=st["driver_id"])

                    prev_cat = self._compound_category(st["current_compound"])
                    pit_loss = self._handle_pit(st, desired, lap, log, track)
                    # Pit duvarı — HAVA PİTİ TETİĞİ: kategori değişti (slick<->yağmur
                    # lastiği) = plan dışı pit; kalan program yeniden kurulur.
                    if (s.PITWALL_ENABLED and pit_loss > 0
                            and self._compound_category(st["current_compound"]) != prev_cat
                            and self._compound_category(st["current_compound"]) == "dry"):
                        self._replan(st, lap, num_laps, tyre_severity, track,
                                     log, "kuruya dönüş")
                    repair_loss = s.REPAIR_TIME if st["pending_repair"] else 0.0
                    st["pending_repair"] = False
                    inc_loss = st["incident_time_loss"]
                    st["incident_time_loss"] = 0.0
                    battle_loss = st["battle_time_loss"]
                    st["battle_time_loss"] *= s.BATTLE_TEMPO_DECAY
                    if st["battle_time_loss"] < 0.005:
                        st["battle_time_loss"] = 0.0
                    st["pit_loss_this_lap"] = pit_loss
                    st["repair_loss_this_lap"] = repair_loss
                    st["incident_loss_this_lap"] = inc_loss
                    st["loss_pit"] += pit_loss
                    st["loss_repair"] += repair_loss
                    st["loss_incident"] += inc_loss
                    st["loss_battle"] += battle_loss

                    comp = s.TYRE_COMPOUNDS[st["current_compound"]]
                    pace_pen, wear_mult = self._tyre_condition(st["current_compound"], wetness)
                    st["wear_pct"] += comp["wear_rate"] * st["tyre_wear_coeff"] * tyre_severity * wear_mult

                    lap_time = self._base_lap_time(st["base_power"], track)
                    lap_time *= (1 - comp["pace"]) * (1 - st["form"]) * (1 + pace_pen) * st["pace_penalty"]
                    lap_time *= (1 + self.rng.gauss(0, self._lap_noise_sigma(st["consistency"])))

                    # Rainmaster: profiller kuru (is_raining=False) kurulduğundan bu perk
                    # dinamik yağmura motor içinde tepki verir (aksi halde hiç çalışmıyordu)
                    if wetness >= 0.15 and "Rainmaster" in st["perks"]:
                        lap_time *= (1 - s.RAINMASTER_WET_PACE)
                        if not st.get("rainmaster_logged"):
                            st["rainmaster_logged"] = True
                            log(lap, "PERK", f"🌧️ Rainmaster devrede: {st['driver_id']} ıslak zeminde hızlanıyor",
                                driver=st["driver_id"], perk="Rainmaster")

                    # Track-position avantajı sadece start fazında uygulanır.
                    # Kalıcı "clean air" bonusu yerine yakın takipteki araçlar aşağıda
                    # dirty-air cezası alır; böylece lider her tur bedava süre kazanmaz.
                    if lap <= s.GRID_ADVANTAGE_FADE_LAPS and i < s.GRID_ADVANTAGE_SPREAD:
                        pos_fade = s.GRID_ADVANTAGE_POS_DECAY ** i
                        diff_scale = ot_difficulty ** s.GRID_ADVANTAGE_DIFFICULTY_POW
                        bonus = s.GRID_START_ADVANTAGE_SEC * (1.0 - (lap - 1) / s.GRID_ADVANTAGE_FADE_LAPS)
                        lap_time -= bonus * diff_scale * pos_fade

                    # Aşınma eğrisi bileşim bazlı: soft erken+sert uçurum, hard geç+yumuşak
                    comp_tc = comp.get("wear_time_coeff", s.WEAR_TIME_COEFF)
                    comp_cliff = comp.get("cliff", s.WEAR_CLIFF)
                    deg = comp_tc * st["wear_pct"]
                    if st["wear_pct"] > comp_cliff:
                        deg += comp.get("cliff_coeff", s.WEAR_CLIFF_COEFF) * (st["wear_pct"] - comp_cliff)
                        
                    if "Bare Canvas" in st["perks"] and st["wear_pct"] > 0.5:
                        deg *= 0.6
                        if not st.get("barecanvas_logged"):
                            st["barecanvas_logged"] = True
                            log(lap, "PERK", f"🛞 Bare Canvas devrede: {st['driver_id']} aşınmış lastikte hızını koruyor",
                                driver=st["driver_id"], perk="Bare Canvas")

                    # Pit kaybı hariç tutulur; geçiş buff'ı pit stop artefaktından değil,
                    # pist üstündeki gerçek tempo/lastik farkından beslensin.
                    # clean_lap_time: sollama modeline giden TEMİZ pace (mücadele/kaza/onarım
                    # kayıpları hariç) — atak yapanın kendi kayıpları kendi şansını düşürmesin.
                    st["clean_lap_time"] = lap_time + deg
                    st["last_lap_time"] = lap_time + deg + repair_loss + inc_loss + battle_loss
                    expected_time = st["cumulative_time"] + lap_time + deg + pit_loss + repair_loss + inc_loss + battle_loss

                    if i > 0:
                        ahead = track_order[i-1]
                        ahead_time = ahead["cumulative_time"]
                        gap_to_ahead = expected_time - ahead_time

                        # Aerodinamik takip etkileri: yalnızca normal seyirde (pit/onarım yokken)
                        # ve gerçekten arkadayken (öndeki araçtan geride) işler.
                        ahead_impeded = (
                            ahead.get("pit_loss_this_lap", 0.0) > 0
                            or ahead.get("repair_loss_this_lap", 0.0) > 0
                            or ahead.get("incident_loss_this_lap", 0.0) > 0
                        )
                        if gap_to_ahead <= 0 and pit_loss == 0 and not ahead_impeded:
                            expected_time = ahead_time + s.MIN_FOLLOW_GAP
                            gap_to_ahead = expected_time - ahead_time

                        if gap_to_ahead > 0 and pit_loss == 0 and not st.get("pending_repair"):
                            drs_eligible = lap >= s.DRS_FROM_LAP and wetness < s.DRS_WET_CUTOFF

                            # 1) Slipstream (tow): düzlükte çekiş etkisi, ~1.5sn içinde,
                            #    DRS'ten bağımsız ve ıslakta da geçerli.
                            if gap_to_ahead <= s.SLIPSTREAM_GAP:
                                expected_time -= s.SLIPSTREAM_TIME_GAIN
                                st["gain_aero"] += s.SLIPSTREAM_TIME_GAIN
                            # 2) DRS: yalnızca 1.0sn içinde ve kuru havada ek kazanç sağlar
                            #    (gerçek hayattaki "1 saniye" kuralı).
                            if drs_eligible and gap_to_ahead <= s.DRS_ACTIVATION_GAP:
                                expected_time -= s.DRS_TIME_GAIN
                                st["gain_aero"] += s.DRS_TIME_GAIN

                            # 3) Kirli hava: 1-2 sn yakın takipte hissedilir ama her tur
                            #    üst üste yazılmaz; cooldown hızlı aracın tekrar kapanmasına izin verir.
                            if gap_to_ahead <= s.DIRTY_AIR_GAP and st["dirty_air_cooldown"] == 0:
                                proximity = 1.0 - (gap_to_ahead / s.DIRTY_AIR_GAP)
                                expected_time += s.DIRTY_AIR_MAX_LOSS * proximity
                                st["loss_dirty_air"] += s.DIRTY_AIR_MAX_LOSS * proximity
                                st["dirty_air_cooldown"] = s.DIRTY_AIR_COOLDOWN_LAPS

                            # 4) Fiziksel minimum: iki araç aynı saniyede aynı noktada olamaz.
                            if expected_time - ahead_time < s.MIN_FOLLOW_GAP:
                                expected_time = ahead_time + s.MIN_FOLLOW_GAP
                            
                    st["cumulative_time"] = expected_time
                    st["laps_completed"] = lap

            # 3) Sollama (Yeşil Bayrakta)
            if sc_laps == 0 and vsc_laps == 0:
                drs_eligible = lap >= s.DRS_FROM_LAP and wetness < s.DRS_WET_CUTOFF
                chaos_lap = lap == 1 or restart_chaos > 0
                ot_bonus = s.START_OVERTAKE_BONUS if chaos_lap else 0.0
                battle_mult = 1.0 + 2.0 * wetness + (2.0 if chaos_lap else 0.0)
                col_caution, col_who, collided = None, None, False

                i = len(track_order) - 1
                while i > 0:
                    ahead, behind = track_order[i-1], track_order[i]
                    gap = behind["cumulative_time"] - ahead["cumulative_time"]

                    if 0 < gap <= s.BATTLE_WINDOW:
                        # DRS yalnızca 1.0sn içindeyse sollama şansına katkı verir.
                        pair_drs = drs_eligible and gap <= s.DRS_ACTIVATION_GAP
                        if self.rng.random() < s.BATTLE_COLLISION_BASE * battle_mult:
                            involved = [behind] + ([ahead] if self.rng.random() < 0.45 else [])
                            worst = "minor"
                            for c in involved:
                                sev = self._apply_crash_outcome(c, lap, log, "sollama teması")
                                if _sev_rank(sev) > _sev_rank(worst): worst = sev
                            k = self._roll_caution(worst, wetness)
                            if _CAUTION_RANK[k] > _CAUTION_RANK[col_caution]:
                                col_caution, col_who = k, behind["driver_id"]
                            collided = True

                        elif self._overtake_success(behind, ahead, ot_difficulty, pair_drs, ot_bonus):
                            track_order[i-1], track_order[i] = behind, ahead
                            behind["cumulative_time"] = ahead["cumulative_time"] - 0.05
                            ahead["cumulative_time"] += 0.15

                            # Tüm pozisyonlar loglanır (UI oyuncunun orta sıra geçişlerini de
                            # gösterebilsin); analiz araçları pos<=10 filtresini kendi uygular.
                            log(lap, "OVERTAKE",
                                f"P{i}: {behind['driver_id']} -> {ahead['driver_id']} geçti"
                                + (" (DRS)" if pair_drs else ""),
                                driver=behind["driver_id"], passed=ahead["driver_id"],
                                pos=i, drs=pair_drs)

                        # Uzayan yakın mücadele: makas BATTLE_WINDOW içinde kaldıkça iki araç
                        # da her tur biraz tempo kaybeder (lastik/fren yıpranması, hat savunması).
                        # battle_time_loss bir sonraki turda tur süresine eklenir, mücadele
                        # bitince BATTLE_TEMPO_DECAY ile kademeli olarak söner.
                        if (behind["running"] and ahead["running"]
                                and gap <= s.BATTLE_WINDOW):
                            # Tur kaybı sabit değil; her mücadele turu farklı sertliktedir
                            battle_hit = self.rng.uniform(s.BATTLE_TEMPO_LOSS_MIN, s.BATTLE_TEMPO_LOSS_MAX)
                            for car in (behind, ahead):
                                car["battle_time_loss"] = min(
                                    s.MAX_BATTLE_TEMPO_LOSS,
                                    car["battle_time_loss"] + battle_hit
                                )
                    i -= 1

                if collided:
                    for st in [x for x in track_order if not x["running"]]:
                        dnf_states.append(st)
                    track_order = [x for x in track_order if x["running"]]
                    if col_caution and not (sc_laps or vsc_laps):
                        if col_caution == "SC":
                            self._bunch_field(track_order, s.SC_INLAP_PENALTY, s.SC_GAP)
                            sc_laps = self.rng.randint(s.SC_LAPS_MIN, s.SC_LAPS_MAX)
                            caution_len = sc_laps
                            log(lap, "SC", f"🟡 GÜVENLİK ARACI ({col_who} teması) — {sc_laps} tur",
                                driver=col_who, laps=sc_laps)
                        elif col_caution == "VSC":
                            vsc_laps = self.rng.randint(s.VSC_LAPS_MIN, s.VSC_LAPS_MAX)
                            caution_len = vsc_laps
                            log(lap, "VSC", f"🟡 VSC ({col_who} teması) — {vsc_laps} tur",
                                driver=col_who, laps=vsc_laps)
                        elif col_caution == "RED":
                            self._bunch_field(track_order, 0.0, 0.0)
                            self._red_flag_free_tyres(track_order, lap, wetness, log)
                            log(lap, "RED_FLAG", f"🔴 KIRMIZI BAYRAK ({col_who} teması) — restart", driver=col_who)
                            if s.PITWALL_ENABLED and wetness < 0.12:
                                for st2 in track_order:
                                    self._replan(st2, lap, num_laps, tyre_severity,
                                                 track, log, "kırmızı bayrak")
                            sc_laps, caution_len = 1, 1

                if track_order and track_order[0]["driver_id"] != prev_leader:
                    log(lap, "LEAD", f"🏁 Yeni lider: {track_order[0]['driver_id']}",
                        driver=track_order[0]["driver_id"])
                    prev_leader = track_order[0]["driver_id"]

                if restart_chaos > 0: restart_chaos -= 1

            if sc_laps > 0:
                sc_laps -= 1
                if sc_laps == 0:
                    restart_chaos = s.RESTART_CHAOS_LAPS + (1 if caution_len >= 4 else 0)
                    log(lap, "RESTART", "🟢 Güvenlik aracı içeri — RESTART, saha sıkışık!", kind="SC")
            elif vsc_laps > 0:
                vsc_laps -= 1
                if vsc_laps == 0:
                    restart_chaos = s.RESTART_CHAOS_LAPS
                    log(lap, "RESTART", "🟢 VSC bitti — yeşil bayrak", kind="VSC")
                    
            track_order = sorted(track_order, key=lambda x: x["cumulative_time"])
            lap_positions.append([st["driver_id"] for st in track_order])

        result = self._classify(track_order, dnf_states)
        result["schema_version"] = SCHEMA_VERSION
        result["seed"] = seed
        result["events"] = events
        result["lap_positions"] = lap_positions
        result["forecast"] = forecast
        result["weather_peak"] = weather_peak
        result["rained"] = rained
        return result

    # ---------------------------------------------------------------- strateji / pit

    def _default_strategy(self, num_laps: int) -> List[Dict[str, Any]]:
        half = max(1, round(num_laps * 0.5))
        return [{"compound": "medium", "laps": half}, {"compound": "hard", "laps": num_laps - half}]

    def _expand_plan(self, plan: List[Dict[str, Any]], num_laps: int,
                     wear_coeff: float = 1.0) -> Dict[int, str]:
        # Stint boyları aracın aşınma karakterine göre ölçeklenir: lastik yiyen araç
        # erken pit eder, lastiğe nazik araç stinti uzatır (son stint kalanı taşır).
        # Oyuncu strateji kartı seçtiğinde de "takım mühendisleri planı araca uyarlar".
        eff = max(0.78, min(1.28, wear_coeff))
        # 1) Stint uzunluklarını araca göre ölçekle
        laps_list = [max(1, round(st["laps"] / eff)) for st in plan[:-1]]
        laps_list.append(max(1, num_laps - sum(laps_list)))
        # 2) MİNİMUM STİNT GARANTİSİ: ölçekleme son stint(ler)i 1-2 tura
        #    sıkıştırabiliyordu (üst üste iki pit, yarış sonunda anlamsız stop).
        #    Kısa kalan stint, en uzun stintten tur çalarak en az MIN_STINT olur;
        #    yarış buna yetmiyorsa kısa stint tamamen İPTAL edilir (önceki yutar).
        MIN_STINT = 5
        if len(laps_list) > 1 and num_laps >= MIN_STINT * len(laps_list):
            for i in range(len(laps_list)):
                while laps_list[i] < MIN_STINT:
                    j = max(range(len(laps_list)), key=lambda k: laps_list[k])
                    if laps_list[j] <= MIN_STINT:
                        break
                    laps_list[j] -= 1
                    laps_list[i] += 1
        kept = [(p["compound"], L) for p, L in zip(plan, laps_list) if L >= MIN_STINT] \
            or [(plan[-1]["compound"], num_laps)]
        compound_by_lap = {}
        lap = 1
        for comp, stint_laps in kept:
            end = min(num_laps, lap + stint_laps - 1)
            for L in range(lap, end + 1):
                compound_by_lap[L] = comp
            lap = end + 1
            if lap > num_laps:
                break
        last_comp = kept[-1][0]
        for L in range(1, num_laps + 1):
            compound_by_lap.setdefault(L, last_comp)
        return compound_by_lap

    def _handle_pit(self, st, desired: str, lap: int, log, track) -> float:
        s = self.settings
        if desired == st["current_compound"]:
            st["pending_switch_lap"] = None
            return 0.0
        same_cat = self._compound_category(st["current_compound"]) == self._compound_category(desired)
        if same_cat:
            do_switch = True
        else:
            if st["pending_switch_lap"] is None:
                st["pending_switch_lap"] = lap + self.rng.randint(0, st["reaction_lag"])
            do_switch = lap >= st["pending_switch_lap"]
        if not do_switch:
            return 0.0
        reason = "hava" if not same_cat else "plan"
        st["current_compound"] = desired
        st["compounds_used"].add(desired)
        st["stint_history"].append({"compound": desired, "from": lap, "reason": reason})
        st["wear_pct"] = 0.0
        st["pits"] += 1
        st["last_pit_lap"] = lap
        st["pending_switch_lap"] = None
        # Hem hava hem PLANLI pitler loglanır (eskiden planlı pitler loglanmıyordu;
        # event akışı/replay/Excel raporunda görünmez kalıyorlardı).
        log(lap, "PIT", f"PIT ({desired}, {reason}): {st['driver_id']}",
            driver=st["driver_id"], compound=desired, reason=reason)


        # Pit süresi varyansı: normal dalgalanma + nadiren yavaş pit (sıkışan bijon vb.)
        pit_time_loss = getattr(track, "pit_loss", None) or s.PIT_LANE_LOSS
        pit_time_loss += self.rng.gauss(0, s.PIT_TIME_SIGMA)
        if self.rng.random() < s.SLOW_PIT_PROB:
            extra = self.rng.uniform(s.SLOW_PIT_EXTRA_MIN, s.SLOW_PIT_EXTRA_MAX)
            pit_time_loss += extra
            log(lap, "SLOW_PIT", f"🔧 Yavaş pit (+{extra:.1f}s): {st['driver_id']} sıkışan bijon!",
                driver=st["driver_id"], extra=round(extra, 2))
        return max(0.0, pit_time_loss)

    # ---------------------------------------------------------------- klasman

    def _classify(self, finishers, dnf_states) -> Dict[str, Any]:
        finishers_sorted = sorted(finishers, key=lambda s: (-s["laps_completed"], s["cumulative_time"]))
        dnf_sorted = sorted(dnf_states, key=lambda s: -s["laps_completed"])
        classification = []
        pos = 1
        for st in finishers_sorted:
            classification.append({
                "driver_id": st["driver_id"], "team_id": st["team_id"], "position": pos,
                "status": "FIN", "laps_completed": st["laps_completed"],
                "total_time": round(st["cumulative_time"], 3),
                "pits": st["pits"], "final_compound": st["current_compound"], "repairs": st["repairs"],
                "stints": st.get("stint_history", []),
                # Analiz: yarış içi kayıp/kazanç dökümü (saniye)
                "loss_breakdown": {
                    "pit": round(st.get("loss_pit", 0.0), 1),
                    "repair": round(st.get("loss_repair", 0.0), 1),
                    "incident": round(st.get("loss_incident", 0.0), 1),
                    "battle": round(st.get("loss_battle", 0.0), 1),
                    "dirty_air": round(st.get("loss_dirty_air", 0.0), 1),
                    "aero_gain": round(st.get("gain_aero", 0.0), 1),
                },
            })
            pos += 1
        for st in dnf_sorted:
            classification.append({
                "driver_id": st["driver_id"], "team_id": st["team_id"], "position": pos,
                "status": "DNF", "laps_completed": st["laps_completed"], "total_time": None,
                "pits": st["pits"], "final_compound": st["current_compound"],
                "stints": st.get("stint_history", []),
                "dnf_cause": st["dnf_cause"], "dnf_detail": st.get("dnf_detail"),
                "repairs": st["repairs"],
            })
            pos += 1
        return {"classification": classification, "dnf_count": len(dnf_states)}


def _sev_rank(sev: str) -> int:
    return {"minor": 0, "damage": 1, "retire": 2}.get(sev, 0)
