import random
import traceback
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn

from app.connection_manager import ConnectionManager
from app.constants import MessageType

app = FastAPI()
templates = Jinja2Templates(directory="templates")

manager = ConnectionManager()
active_users = {}
is_count_down_working = False
correct_answer = 0
user_score_map = defaultdict(int)


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login/", response_class=HTMLResponse)
async def post(request: Request):
    form_data = await request.form()
    user_id = form_data.get("user_id")  # 특정 필드 값 가져오기

    context = {
        "request": request,  # 반드시 포함되어야 함
        "user_id": user_id,
    }
    if user_id == "admin@admin.com":
        return templates.TemplateResponse("admin.html", context)

    return templates.TemplateResponse("vote_ground.html", context)

@app.post("/status/", response_class=HTMLResponse)
async def post(request: Request):
    global active_users

    user_states = [{"user_id": user_id, "status": datas['websocket'].client_state} for user_id, datas in active_users.items()]

    context = {
        "request": request,  # 반드시 포함되어야 함
        "user_states": user_states,
    }
    return templates.TemplateResponse("admin.html", context)

@app.post("/reset/", response_class=HTMLResponse)
async def post(request: Request):
    global active_users
    global user_score_map
    global correct_answer

    manager.all_disconnect()

    del active_users
    del user_score_map
    correct_answer = 0
    active_users = {}
    user_score_map = defaultdict(int)

    context = {
        "request": request,  # 반드시 포함되어야 함
    }
    return templates.TemplateResponse("admin.html", context)


@app.post("/notice/", response_class=HTMLResponse)
async def post(request: Request):
    form_data = await request.form()
    notice_content = form_data.get("notice_content")  # 특정 필드 값 가져오기

    await manager.broadcast(
        {
            "type": MessageType.NOTICE,
            "content": notice_content,
        }
    )

    context = {
        "request": request,  # 반드시 포함되어야 함
    }
    return templates.TemplateResponse("admin.html", context)

@app.post("/result/", response_class=HTMLResponse)
async def post(request: Request):
    results = []
    for user_id, score in user_score_map.items():
        results.append(
            {"user_id": user_id, "score": score}
        )

    zero_users = set(active_users.keys()) - set(user_score_map.keys())
    for zero_user_id in zero_users:
        results.append(
            {"user_id": zero_user_id, "score": 0}
        )

    await manager.broadcast(
        {
            "type": MessageType.RESULT,
            "results": results,
        }
    )

    context = {
        "request": request,  # 반드시 포함되어야 함
        "results": results,
    }
    return templates.TemplateResponse("admin.html", context)


@app.post("/countdown/", response_class=HTMLResponse)
async def post(request: Request):
    global is_count_down_working
    global correct_answer
    is_count_down_working = True

    form_data = await request.form()
    count_down_value = form_data.get("count_down")
    correct_answer = int(form_data.get("correct_answer"))

    await manager.broadcast(
        {
            "type": MessageType.COUNT_DOWN,
            "value": count_down_value,
        }
    )

    context = {
        "request": request,  # 반드시 포함되어야 함
    }
    return templates.TemplateResponse("admin.html", context)


def generate_random_color():
    """랜덤한 HEX 색상 생성"""
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))


vote_results = defaultdict(list)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    _user_id = None
    try:
        # 3. 메시지 처리 루프
        while True:
            data = await websocket.receive_json()
            data_type = data["type"]
            user_id = data["user_id"]
            _user_id = user_id
            if data_type == MessageType.LOGIN:
                # 새 사용자 추가
                color = generate_random_color()
                active_users[user_id] = {
                    "websocket": websocket,
                    "x": random.randint(-300, 300),  # x 좌표: -100 ~ 100
                    "y": random.randint(-300, 300),  # y 좌표: -100 ~ 100
                    "color": color,
                }

                # 1. 초기화: 새 사용자에게 현재 접속 중인 사용자 정보 전송
                await websocket.send_json(
                    {
                        "type": MessageType.INIT,
                        "user_id": user_id,
                        "users": [
                            {
                                "user_id": uid,
                                "x": data["x"],
                                "y": data["y"],
                                "color": data["color"],
                            }
                            for uid, data in active_users.items()
                        ],
                    }
                )
                # 2. 다른 사용자들에게 새 사용자 입장 알림
                await manager.broadcast(
                    {
                        "type": MessageType.USER_JOIN,
                        "user_id": user_id,
                        "x": 0,
                        "y": 0,
                        "color": color,
                    }
                )

            elif data_type == MessageType.USER_MOVE:
                # 사용자 위치 업데이트
                active_users[user_id]["x"] = data["x"]
                active_users[user_id]["y"] = data["y"]

                # 다른 사용자들에게 이동 정보 브로드캐스트
                await manager.broadcast(
                    {
                        "type": MessageType.USER_MOVE,
                        "user_id": user_id,
                        "x": data["x"],
                        "y": data["y"],
                    }
                )
            elif data["type"] == MessageType.COUNT_DOWN_END:
                global is_count_down_working
                if is_count_down_working:
                    is_count_down_working = False

                    for zone_id, uids in vote_results.items():
                        if int(zone_id) != correct_answer:
                            continue

                        for uid in uids:
                            user_score_map[uid] += 10

                        await manager.broadcast(
                            {
                                "type": MessageType.SHOW_ANSWER,
                                "user_ids": uids,
                            }
                        )
                    # 점수 채점

            elif data["type"] == MessageType.ZONE_IN:
                vote_results[data["zone_id"]].append(_user_id)

            elif data["type"] == MessageType.ZONE_LEAVE:
                for zone_id, uids in vote_results.items():
                    if _user_id in uids:
                        uids.remove(_user_id)
                        vote_results[zone_id] = uids

            elif data["type"] == MessageType.CHAT:
                # 이모지 이벤트 처리
                emoji = data.get("chat")
                await manager.broadcast(
                    message={
                        "type": MessageType.CHAT,
                        "user_id": user_id,
                        "chat": emoji,
                    },
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        del active_users[_user_id]
        await manager.broadcast({"type": MessageType.USER_LEAVE, "user_id": _user_id})
    except Exception as e:
        traceback.print_exc()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
