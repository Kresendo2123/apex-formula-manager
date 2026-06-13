// Apex Formula Manager — istemci/sunucu sözleşmesi sabitleri (Faz 2, dilim 1).
// Kaynak: server/protocol.py — buradaki adlar oradakiyle BİREBİR eşleşmeli.
namespace Apex.Net
{
    public static class Protocol
    {
        public const int PROTOCOL_VERSION = 1;

        // İstemci -> sunucu (op)
        public const string OP_CREATE_ROOM     = "create_room";
        public const string OP_JOIN_ROOM       = "join_room";
        public const string OP_PICK_TEAM       = "pick_team";
        public const string OP_READY           = "ready";
        public const string OP_START_GAME      = "start_game";
        public const string OP_SUBMIT_AERO     = "submit_aero";
        public const string OP_SUBMIT_STRATEGY = "submit_strategy";
        public const string OP_SUBMIT_UPGRADES = "submit_upgrades";
        public const string OP_SYNC            = "sync";
        public const string OP_LIST_TEAMS      = "list_teams";

        // Sunucu -> istemci (ev)
        public const string EV_HELLO            = "hello";
        public const string EV_TEAM_CATALOG     = "team_catalog";
        public const string EV_JOINED           = "joined";
        public const string EV_ROOM             = "room";
        public const string EV_STATIC_DATA      = "static_data";
        public const string EV_PHASE            = "phase";
        public const string EV_QUALI_RESULT     = "quali_result";
        public const string EV_RACE_RESULT      = "race_result";
        public const string EV_STANDINGS        = "standings";
        public const string EV_SUBMIT_OK        = "submit_ok";
        public const string EV_PLAYER_SUBMITTED = "player_submitted";
        public const string EV_AUTO_FILLED      = "auto_filled";
        public const string EV_ERROR            = "error";

        // Hata kodları
        public const string ERR_BAD_MESSAGE    = "bad_message";
        public const string ERR_NOT_IN_ROOM    = "not_in_room";
        public const string ERR_ROOM_NOT_FOUND = "room_not_found";
        public const string ERR_ROOM_FULL      = "room_full";
        public const string ERR_ROOM_STARTED   = "room_started";
        public const string ERR_NOT_HOST       = "not_host";
        public const string ERR_NOT_READY      = "not_ready";
        public const string ERR_TEAM_TAKEN     = "team_taken";
        public const string ERR_SUBMIT         = "submit_rejected";

        public const int MAX_PLAYERS = 11;

        // Hata kodu -> kullanıcıya gösterilecek Türkçe mesaj.
        public static string FriendlyError(string code, string fallback)
        {
            switch (code)
            {
                case ERR_ROOM_NOT_FOUND: return "Oda bulunamadı.";
                case ERR_ROOM_FULL:      return "Oda dolu (11 oyuncu).";
                case ERR_ROOM_STARTED:   return "Oyun zaten başladı.";
                case ERR_NOT_HOST:       return "Yalnızca oda sahibi başlatabilir.";
                case ERR_NOT_READY:      return "Herkes takım seçip hazır olmalı.";
                case ERR_TEAM_TAKEN:     return "Bu takım başka oyuncuda.";
                case ERR_SUBMIT:         return "Gönderim reddedildi.";
                case ERR_NOT_IN_ROOM:    return "Önce bir odaya katıl.";
                default:                 return string.IsNullOrEmpty(fallback) ? code : fallback;
            }
        }
    }
}
