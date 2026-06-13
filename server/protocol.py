"""
WebSocket mesaj protokolü (Faz 1) — istemci/sunucu sözleşmesinin taşıma katmanı.

Tüm mesajlar JSON'dur. İstemci -> sunucu mesajları "op", sunucu -> istemci
mesajları "ev" alanı taşır. Yarış olaylarının içeriği ayrı sürümlenir
(docs/EVENT_SCHEMA.md, result.schema_version); buradaki PROTOCOL_VERSION
yalnız zarf/akış mesajlarını kapsar.

İSTEMCİ -> SUNUCU (op)
  create_room   {name, opts?: {num_races?, turn_seconds?, dynamic_ai?, seed?}}
  join_room     {code, name, rejoin_token?}
  pick_team     {team_id}
  ready         {ready: bool}
  start_game    {}                      (yalnız host; herkes takım seçmiş + hazır)
  submit_aero   {level: 1-5}
  submit_strategy {choices: {driver_id: {card_id?, style?, wall?}}}
  submit_upgrades {spends: [...], facility?}   (bkz. SeasonSession.submit_upgrades)
  sync          {}                      (durumu yeniden iste — reconnect sonrası)
  list_teams    {}                      (oyun-öncesi takım kataloğu; odaya gerek yok)

SUNUCU -> İSTEMCİ (ev)
  hello         {protocol_version, schema_version}
  team_catalog  {teams: [{id, name, drivers: [isim,...]}]}   (list_teams yanıtı)
  joined        {player_id, rejoin_token, room}      (yalnız katılan oyuncuya)
  room          {code, host, started, players: [{name, team_id, ready, connected}]}
  static_data   {teams, drivers, calendar, styles, ...}   (oyun başlarken)
  phase         {race_no, total_races, phase, pending_teams, deadline_ts?, ...bağlam}
  quali_result  {race_no, is_rain, grid}
  race_result   {race_no, track, grid, result}   (result = motor çıktısı, events dahil)
  standings     {drivers, teams}
  submit_ok     {phase}                          (yalnız gönderen oyuncuya)
  player_submitted {team_id, phase}              (ilerleme göstergesi)
  auto_filled   {teams, phase}                   (zaman aşımında doldurulanlar)
  error         {code, msg}

Kurallar:
- Bilinmeyen "ev" tipi istemcide yok sayılır (ileri uyumluluk).
- "deadline_ts" Unix epoch saniyesidir; karar fazlarında bulunur. Süre dolunca
  sunucu eksik girdileri otomatik doldurur ve oyunu ilerletir (oyun kilitlenmez).
- Yarış içi etkileşim YOKTUR: race_result tek parça gelir, istemci
  result.events akışını kendi temposunda replay olarak oynatır.
"""

PROTOCOL_VERSION = 1

# Hata kodları
ERR_BAD_MESSAGE = "bad_message"
ERR_NOT_IN_ROOM = "not_in_room"
ERR_ROOM_NOT_FOUND = "room_not_found"
ERR_ROOM_FULL = "room_full"
ERR_ROOM_STARTED = "room_started"
ERR_NOT_HOST = "not_host"
ERR_NOT_READY = "not_ready"
ERR_TEAM_TAKEN = "team_taken"
ERR_SUBMIT = "submit_rejected"

DEFAULT_TURN_SECONDS = 90
MAX_PLAYERS = 11
