from enum import StrEnum


class MessageType(StrEnum):
    LOGIN = "login"
    INIT = "init"
    USER_JOIN = "user_join"
    USER_MOVE = 'user_move'
    USER_LEAVE = 'user_leave'
    COUNT_DOWN = 'count_down'
    COUNT_DOWN_END = 'count_down_end'
    ZONE_IN = 'zone_in'
    ZONE_LEAVE = 'zone_leave'
    SHOW_ANSWER = 'show_answer'
    RESULT = 'result'
    CHAT = "chat"
