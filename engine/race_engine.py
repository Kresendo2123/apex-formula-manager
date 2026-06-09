import random
from typing import List, Dict, Any, Optional


# Caution (neutralizasyon) şiddet sıralaması
_CAUTION_RANK = {None: 0, "VSC": 1, "SC": 2, "RED": 3}


class LapRaceEngine:
    """
    Tur tur (lap-by-lap) yarış motoru.
    """

    def __init__(self, settings):
        self.settings = settings

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
        return 0.7 + track.req_grip * 0.9

    # ---------------------------------------------------------------- hava tahmini

    def make_forecast(self, track, num_laps: int) -> Dict[str, Any]:
        s = self.settings
        rain_prob = min(0.92, track.weather_volatility * s.RAIN_EVENT_SCALE)
        exp_start = random.randint(max(1, num_laps // 5), max(2, int(num_laps * 0.7)))
        exp_intensity = random.uniform(0.40, 0.95)
        exp_duration = random.randint(5, max(6, num_laps // 2))
        label = (f"%{rain_prob * 100:.0f} yağış olasılığı, ~{exp_start}. turda, "
                 f"şiddet {exp_intensity:.2f}, ~{exp_duration} tur sürmesi bekleniyor"
                 if rain_prob > 0.05 else "kuru, yağış beklenmiyor")
        return {"rain_prob": rain_prob, "exp_start": exp_start, "exp_intensity": exp_intensity,
                "exp_duration": exp_duration, "confidence": s.FORECAST_CONFIDENCE, "label": label}

    def _realize_weather(self, forecast: Dict[str, Any], num_laps: int):
        wet = [0.0] * (num_laps + 2)
        if random.random() >= forecast["rain_prob"]:
            return wet, 0.0, False
        conf = forecast["confidence"]
        start = int(round(forecast["exp_start"] + random.gauss(0, (1 - conf) * 8)))
        start = max(1, min(num_laps - 2, start))
        peak = max(0.30, min(1.0, forecast["exp_intensity"] * (1 + random.gauss(0, (1 - conf) * 0.4))))
        dur = max(3, int(round(forecast["exp_duration"] + random.gauss(0, (1 - conf) * 6))))
        ramp = random.randint(2, 5)
        for i in range(num_laps + 2):
            if i < start:
                w = 0.0
            elif i < start + ramp:
                w = peak * (i - start + 1) / ramp
            elif i < start + ramp + dur:
                w = peak
            else:
                w = peak - (i - (start + ramp + dur)) * peak / max(1, ramp)
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

    def _desired_category(self, wetness: float, wet_bias: float = 0.0) -> str:
        s = self.settings
        if wetness >= s.WET_TYRE_THRESHOLD + wet_bias: return "wet"
        if wetness >= s.DRY_TYRE_WET_THRESHOLD + wet_bias: return "inter"
        return "dry"

    def _desired_compound(self, planned_dry: str, wetness: float, wet_bias: float) -> str:
        cat = self._desired_category(wetness, wet_bias)
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
        roll = random.random()
        if roll < s.CRASH_RETIRE_PROB:
            st["running"] = False
            st["dnf_lap"] = lap
            st["dnf_cause"] = "crash"
            log(lap, "DNF", f"DNF (KAZA, {context}): {st['driver_id']}", driver=st["driver_id"], cause="crash")
            return "retire"
        if roll < s.CRASH_RETIRE_PROB + s.CRASH_DAMAGE_PROB:
            st["pending_repair"] = True
            st["pace_penalty"] *= (1 + s.DAMAGE_PACE_PENALTY)
            st["repairs"] += 1
            log(lap, "DAMAGE", f"Hasarlı ({context}): {st['driver_id']} pite girip onarıyor, devam",
                driver=st["driver_id"])
            return "damage"
        st["incident_time_loss"] += s.MINOR_TIME_LOSS
        log(lap, "SPIN", f"Spin/çıkış ({context}): {st['driver_id']} zaman kaybetti", driver=st["driver_id"])
        return "minor"

    def _roll_caution(self, severity: str, wetness: float):
        s = self.settings
        if severity == "retire":
            r = random.random()
            sc_p = s.SC_FROM_CRASH_PROB + s.SC_WET_BONUS * wetness
            if r < s.RED_FLAG_PROB: return "RED"
            if r < s.RED_FLAG_PROB + sc_p: return "SC"
            if r < s.RED_FLAG_PROB + sc_p + s.VSC_FROM_CRASH_PROB: return "VSC"
            return None
        if severity == "damage":
            return "VSC" if random.random() < s.VSC_FROM_DAMAGE_PROB else None
        return None

    def _resolve_mech(self, st, lap, num_laps, log):
        s = self.settings
        if lap >= num_laps * s.LIMP_WINDOW and random.random() < s.LATE_LIMP_PROB:
            st["pace_penalty"] *= (1 + s.LIMP_PACE_PENALTY)
            log(lap, "LIMP", f"Mekanik sorun: {st['driver_id']} topallayarak devam (hız/sıra kaybı)", driver=st["driver_id"])
            return None
        if random.random() < s.MECH_RETIRE_PROB:
            st["running"] = False
            st["dnf_lap"] = lap
            st["dnf_cause"] = "mech"
            log(lap, "DNF", f"DNF (arıza): {st['driver_id']}", driver=st["driver_id"], cause="mech")
            return "VSC" if random.random() < s.VSC_FROM_MECH_PROB else None
        st["pending_repair"] = True
        st["pace_penalty"] *= (1 + s.DAMAGE_PACE_PENALTY * 0.5)
        st["repairs"] += 1
        log(lap, "REPAIR", f"Parça değişimi pit'i: {st['driver_id']} devam ediyor", driver=st["driver_id"])
        return None

    def _bunch_field(self, track_order, anchor_extra: float, gap: float):
        if not track_order:
            return
        ordered = sorted(track_order, key=lambda s: s["cumulative_time"])
        base = ordered[0]["cumulative_time"] + anchor_extra
        for i, st in enumerate(ordered):
            st["cumulative_time"] = base + i * gap

    def _overtake_success(self, attacker, defender, ot_difficulty, drs_on, extra_bonus=0.0) -> bool:
        s = self.settings
        pilot_diff = (attacker["attack_defense"] - defender["attack_defense"]) / 100.0 * 0.15
        power_diff = (attacker["base_power"] - defender["base_power"]) * 0.02
        tire_diff = (defender["wear_pct"] - attacker["wear_pct"]) * 0.20
        
        prob = s.BASE_OVERTAKE_CHANCE * (1 - ot_difficulty)
        prob += pilot_diff + power_diff + tire_diff
        
        if drs_on: prob += s.DRS_BOOST
        prob += extra_bonus
        
        return random.random() < max(0.01, min(0.99, prob))

    # ---------------------------------------------------------------- ana döngü

    def simulate_race(self, grid_order: List[str], profiles: Dict[str, Dict[str, Any]],
                      track, num_laps: Optional[int] = None,
                      strategies: Optional[Dict[str, Any]] = None,
                      form: Optional[Dict[str, float]] = None,
                      forecast: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = self.settings
        form = form or {}
        strategies = strategies or {}
        if num_laps is None:
            num_laps = getattr(track, "num_laps", None) or s.DEFAULT_RACE_LAPS

        if forecast is None:
            forecast = self.make_forecast(track, num_laps)
        weather, weather_peak, rained = self._realize_weather(forecast, num_laps)

        ot_difficulty = self._track_overtaking_difficulty(track)
        tyre_severity = self._track_tyre_severity(track)
        events: List[Dict[str, Any]] = []

        def log(lap, etype, msg, **kw):
            ev = {"lap": lap, "type": etype, "msg": msg}
            ev.update(kw)
            events.append(ev)

        states = {}
        for grid_idx, d_id in enumerate(grid_order):
            p = profiles[d_id]
            strat = strategies.get(d_id)
            if isinstance(strat, list):
                plan, wet_bias, reaction_lag = strat, 0.0, s.WEATHER_REACTION_LAG
            elif isinstance(strat, dict):
                plan = strat["plan"]
                wet_bias = strat.get("wet_bias", 0.0)
                reaction_lag = strat.get("reaction_lag", s.WEATHER_REACTION_LAG)
            else:
                plan = self._default_strategy(num_laps)
                wet_bias, reaction_lag = 0.0, s.WEATHER_REACTION_LAG
            compound_by_lap = self._expand_plan(plan, num_laps)
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
                "wear_pct": 0.0, "pits": 0, "wet_bias": wet_bias, "reaction_lag": reaction_lag,
                "pending_switch_lap": None,
                "pace_penalty": 1.0, "pending_repair": False, "incident_time_loss": 0.0, "repairs": 0,
                "battle_time_loss": 0.0, "pit_loss_this_lap": 0.0,
                "repair_loss_this_lap": 0.0, "incident_loss_this_lap": 0.0,
            }

        track_order = [states[d_id] for d_id in grid_order]
        dnf_states = []
        sc_laps = vsc_laps = 0
        caution_len = 0
        restart_chaos = 0
        prev_leader = track_order[0]["driver_id"] if track_order else None
        prev_band = self._weather_label(weather[1] if len(weather) > 1 else 0.0)

        log(0, "FORECAST", f"Hava tahmini: {forecast['label']}")
        log(0, "START", f"Yarış başladı — pole: {prev_leader} | başlangıç: {prev_band} | {num_laps} tur",
            driver=prev_leader)

        track_base_time = getattr(track, "base_lap_time", None) or s.BASE_LAP_TIME

        for lap in range(1, num_laps + 1):
            wetness = weather[lap]
            band = self._weather_label(wetness)
            if band != prev_band:
                verb = "kötüleşiyor" if self._band_rank(band) > self._band_rank(prev_band) else "düzeliyor"
                log(lap, "WEATHER", f"Hava: {prev_band} -> {band} ({verb}, ıslaklık {wetness:.2f})",
                    wetness=wetness, band=band)
                prev_band = band

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
                    roll = random.random()
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
                    for st in track_order:
                        st["current_compound"] = self._desired_compound(
                            st["compound_by_lap"][lap], wetness, st["wet_bias"])
                        st["wear_pct"] = 0.0
                    log(lap, "RED_FLAG", f"🔴 KIRMIZI BAYRAK ({req_who}) — yarış durdu, restart", driver=req_who)
                    sc_laps, caution_len = 1, 1
                elif req_caution == "SC":
                    self._bunch_field(track_order, s.SC_INLAP_PENALTY, s.SC_GAP)
                    sc_laps = random.randint(s.SC_LAPS_MIN, s.SC_LAPS_MAX)
                    caution_len = sc_laps
                    log(lap, "SC", f"🟡 GÜVENLİK ARACI ({req_who}) — saha toplandı, {sc_laps} tur", driver=req_who)
                else:
                    vsc_laps = random.randint(s.VSC_LAPS_MIN, s.VSC_LAPS_MAX)
                    caution_len = vsc_laps
                    log(lap, "VSC", f"🟡 VSC ({req_who}) — {vsc_laps} tur", driver=req_who)
                under_caution = True

            # 2) Tur süreleri
            if sc_laps > 0:
                sc_time = track_base_time * s.SC_SPEED_MULT
                for st in track_order:
                    st["cumulative_time"] += sc_time
                    st["wear_pct"] += s.TYRE_COMPOUNDS[st["current_compound"]]["wear_rate"] * st["tyre_wear_coeff"] * tyre_severity * 0.2
                    st["laps_completed"] = lap
            elif vsc_laps > 0:
                for st in track_order:
                    st["cumulative_time"] += self._base_lap_time(st["base_power"], track) * s.VSC_SLOWDOWN
                    st["laps_completed"] = lap
            else:
                for i, st in enumerate(track_order):
                    desired = self._desired_compound(st["compound_by_lap"][lap], wetness, st["wet_bias"])
                    pit_loss = self._handle_pit(st, desired, lap, log, track)
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

                    comp = s.TYRE_COMPOUNDS[st["current_compound"]]
                    pace_pen, wear_mult = self._tyre_condition(st["current_compound"], wetness)
                    st["wear_pct"] += comp["wear_rate"] * st["tyre_wear_coeff"] * tyre_severity * wear_mult

                    lap_time = self._base_lap_time(st["base_power"], track)
                    lap_time *= (1 - comp["pace"]) * (1 - st["form"]) * (1 + pace_pen) * st["pace_penalty"]
                    lap_time *= (1 + random.gauss(0, self._lap_noise_sigma(st["consistency"])))

                    # Track-position avantajı: öndeki araç temiz havada + iyi kalkış yaşar.
                    # MEVCUT pozisyona (i) bağlı, SABİT SANİYE (uzun turlu pistler orantısız
                    # avantaj almasın) ve pistin GEÇİŞ ZORLUĞUYLA ölçekli (zor pistte track
                    # position değerli). İki bileşen: START (tura göre söner) + CLEAN-AIR
                    # (kalıcı, pit sonrası da liderliği korur). Pozisyona göre ÜSTEL azalır.
                    if i < s.GRID_ADVANTAGE_SPREAD:
                        pos_fade = s.GRID_ADVANTAGE_POS_DECAY ** i
                        diff_scale = ot_difficulty ** s.GRID_ADVANTAGE_DIFFICULTY_POW
                        bonus = s.CLEAN_AIR_ADVANTAGE_SEC
                        if lap <= s.GRID_ADVANTAGE_FADE_LAPS:
                            bonus += s.GRID_START_ADVANTAGE_SEC * (1.0 - (lap - 1) / s.GRID_ADVANTAGE_FADE_LAPS)
                        lap_time -= bonus * diff_scale * pos_fade

                    deg = s.WEAR_TIME_COEFF * st["wear_pct"]
                    if st["wear_pct"] > s.WEAR_CLIFF:
                        deg += s.WEAR_CLIFF_COEFF * (st["wear_pct"] - s.WEAR_CLIFF)
                        
                    if "Bare Canvas" in st["perks"] and st["wear_pct"] > 0.5:
                        deg *= 0.6

                    expected_time = st["cumulative_time"] + lap_time + deg + pit_loss + repair_loss + inc_loss + battle_loss

                    if i > 0:
                        ahead = track_order[i-1]
                        ahead_time = ahead["cumulative_time"]
                        gap_to_ahead = expected_time - ahead_time

                        # Aerodinamik takip etkileri: yalnızca normal seyirde (pit/onarım yokken)
                        # ve gerçekten arkadayken (öndeki araçtan geride) işler.
                        if gap_to_ahead > 0 and pit_loss == 0 and not st.get("pending_repair"):
                            drs_eligible = lap >= s.DRS_FROM_LAP and wetness < s.DRS_WET_CUTOFF

                            # 1) Slipstream (tow): düzlükte çekiş etkisi, ~1.5sn içinde,
                            #    DRS'ten bağımsız ve ıslakta da geçerli.
                            if gap_to_ahead <= s.SLIPSTREAM_GAP:
                                expected_time -= s.SLIPSTREAM_TIME_GAIN
                            # 2) DRS: yalnızca 1.0sn içinde ve kuru havada ek kazanç sağlar
                            #    (gerçek hayattaki "1 saniye" kuralı).
                            if drs_eligible and gap_to_ahead <= s.DRS_ACTIVATION_GAP:
                                expected_time -= s.DRS_TIME_GAIN

                            # 3) Kirli hava: öndeki araca çok yakınsa virajlarda downforce
                            #    kaybeder ve tempo düşer. Yakınlık arttıkça (gap küçüldükçe)
                            #    kayıp büyür; bu da peşe takılıp geçememe hissini yaratır.
                            if gap_to_ahead <= s.DIRTY_AIR_GAP:
                                proximity = 1.0 - (gap_to_ahead / s.DIRTY_AIR_GAP)
                                expected_time += s.DIRTY_AIR_MAX_LOSS * proximity

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

                    if 0 < gap <= 1.2:
                        # DRS yalnızca 1.0sn içindeyse sollama şansına katkı verir.
                        pair_drs = drs_eligible and gap <= s.DRS_ACTIVATION_GAP
                        if random.random() < s.BATTLE_COLLISION_BASE * battle_mult:
                            involved = [behind] + ([ahead] if random.random() < 0.45 else [])
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
                            behind["cumulative_time"] = ahead["cumulative_time"] - 0.2
                            ahead["cumulative_time"] += 0.4

                            if i <= 10:
                                log(lap, "OVERTAKE",
                                    f"P{i}: {behind['driver_id']} -> {ahead['driver_id']} geçti"
                                    + (" (DRS)" if pair_drs else ""),
                                    driver=behind["driver_id"], passed=ahead["driver_id"], pos=i)

                        # Uzayan yakın mücadele: makas BATTLE_WINDOW içinde kaldıkça iki araç
                        # da her tur biraz tempo kaybeder (lastik/fren yıpranması, hat savunması).
                        # battle_time_loss bir sonraki turda tur süresine eklenir, mücadele
                        # bitince BATTLE_TEMPO_DECAY ile kademeli olarak söner.
                        if (behind["running"] and ahead["running"]
                                and gap <= s.BATTLE_WINDOW):
                            for car in (behind, ahead):
                                car["battle_time_loss"] = min(
                                    s.MAX_BATTLE_TEMPO_LOSS,
                                    car["battle_time_loss"] + s.BATTLE_TEMPO_LOSS
                                )
                    i -= 1

                if collided:
                    for st in [x for x in track_order if not x["running"]]:
                        dnf_states.append(st)
                    track_order = [x for x in track_order if x["running"]]
                    if col_caution and not (sc_laps or vsc_laps):
                        if col_caution == "SC":
                            self._bunch_field(track_order, s.SC_INLAP_PENALTY, s.SC_GAP)
                            sc_laps = random.randint(s.SC_LAPS_MIN, s.SC_LAPS_MAX)
                            caution_len = sc_laps
                            log(lap, "SC", f"🟡 GÜVENLİK ARACI ({col_who} teması) — {sc_laps} tur", driver=col_who)
                        elif col_caution == "VSC":
                            vsc_laps = random.randint(s.VSC_LAPS_MIN, s.VSC_LAPS_MAX)
                            caution_len = vsc_laps
                            log(lap, "VSC", f"🟡 VSC ({col_who} teması) — {vsc_laps} tur", driver=col_who)
                        elif col_caution == "RED":
                            self._bunch_field(track_order, 0.0, 0.0)
                            log(lap, "RED_FLAG", f"🔴 KIRMIZI BAYRAK ({col_who} teması) — restart", driver=col_who)
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
                    log(lap, "RESTART", "🟢 Güvenlik aracı içeri — RESTART, saha sıkışık!")
            elif vsc_laps > 0:
                vsc_laps -= 1
                if vsc_laps == 0:
                    restart_chaos = s.RESTART_CHAOS_LAPS
                    log(lap, "RESTART", "🟢 VSC bitti — yeşil bayrak")
                    
            track_order = sorted(track_order, key=lambda x: x["cumulative_time"])

        result = self._classify(track_order, dnf_states)
        result["events"] = events
        result["forecast"] = forecast
        result["weather_peak"] = weather_peak
        result["rained"] = rained
        return result

    # ---------------------------------------------------------------- strateji / pit

    def _default_strategy(self, num_laps: int) -> List[Dict[str, Any]]:
        half = max(1, round(num_laps * 0.5))
        return [{"compound": "medium", "laps": half}, {"compound": "hard", "laps": num_laps - half}]

    def _expand_plan(self, plan: List[Dict[str, Any]], num_laps: int) -> Dict[int, str]:
        compound_by_lap = {}
        lap = 1
        for idx, stint in enumerate(plan):
            is_last = idx == len(plan) - 1
            end = num_laps if is_last else min(num_laps, lap + stint["laps"] - 1)
            for L in range(lap, end + 1):
                compound_by_lap[L] = stint["compound"]
            lap = end + 1
            if lap > num_laps:
                break
        last_comp = plan[-1]["compound"]
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
                st["pending_switch_lap"] = lap + random.randint(0, st["reaction_lag"])
            do_switch = lap >= st["pending_switch_lap"]
        if not do_switch:
            return 0.0
        reason = "hava" if not same_cat else "plan"
        st["current_compound"] = desired
        st["wear_pct"] = 0.0
        st["pits"] += 1
        st["pending_switch_lap"] = None
        if reason == "hava":
            log(lap, "PIT", f"PIT ({desired}, hava): {st['driver_id']}", driver=st["driver_id"], compound=desired)
            
        pit_time_loss = getattr(track, "pit_loss", None) or s.PIT_LANE_LOSS
        return pit_time_loss

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
            })
            pos += 1
        for st in dnf_sorted:
            classification.append({
                "driver_id": st["driver_id"], "team_id": st["team_id"], "position": pos,
                "status": "DNF", "laps_completed": st["laps_completed"], "total_time": None,
                "pits": st["pits"], "final_compound": st["current_compound"],
                "dnf_cause": st["dnf_cause"], "repairs": st["repairs"],
            })
            pos += 1
        return {"classification": classification, "dnf_count": len(dnf_states)}


def _sev_rank(sev: str) -> int:
    return {"minor": 0, "damage": 1, "retire": 2}.get(sev, 0)
