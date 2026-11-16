from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .store import Problem


def install(app, center, templates, context):
    @app.middleware("http")
    async def qa_access(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health":
            # Legacy write paths cannot bypass reviews, roles, runner reservation or mail policy.
            if not path.startswith("/api/qa/") and request.method not in ("GET", "HEAD"):
                return JSONResponse({"error": "旧写入接口已停用，请使用 /api/qa 产品接口"}, status_code=410)
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            try:
                request.state.actor = center.store.actor(token)
            except Problem as exc:
                return JSONResponse({"error": exc.message}, status_code=exc.status)
            if not path.startswith("/api/qa/") and request.state.actor["role"] == "rd":
                return JSONResponse({"error": "RD请使用按归属过滤的新接口"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(Problem)
    async def problem(request, exc):
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.get("/api/qa/me")
    def me(request: Request):
        return request.state.actor

    @app.post("/api/qa/requirements/import")
    async def import_requirement(request: Request):
        name = request.query_params.get("filename") or request.headers.get("x-filename") or "requirement.txt"
        owner = request.query_params.get("owner", "文档导入")
        area = request.query_params.get("area", "需求文档")
        priority = request.query_params.get("priority", "P1")
        demo = request.query_params.get("demo", "false").lower() == "true"
        return await run_in_threadpool(
            center.import_requirement_document, request.state.actor, name, await request.body(),
            {"owner": owner, "area": area, "priority": priority, "demo": demo})

    @app.get("/api/qa/outbox/{mail_id}/download")
    @app.get("/api/qa/outbox/{mail_id}/eml")
    def download(mail_id: str, request: Request):
        return Response(center.eml(request.state.actor, mail_id), media_type="message/rfc822",
                        headers={"Content-Disposition": f'attachment; filename="{mail_id}.eml"'})

    @app.get("/api/qa/{collection}")
    def listing(collection: str, request: Request):
        return center.snapshot(request.state.actor, collection)

    @app.get("/api/qa/{collection}/{object_id}")
    def detail(collection: str, object_id: str, request: Request):
        items = center.snapshot(request.state.actor, collection)
        if isinstance(items, list):
            for item in items:
                if item["id"] == object_id:
                    return item
        raise Problem("对象不存在", 404)

    @app.post("/api/qa/{collection}")
    async def create(collection: str, request: Request):
        return await run_in_threadpool(center.dispatch, request.state.actor, collection, None,
                                      "create", await request.json())

    @app.post("/api/qa/{collection}/{object_id}/{action}")
    async def action(collection: str, object_id: str, action: str, request: Request):
        return await run_in_threadpool(center.dispatch, request.state.actor, collection,
                                      None if object_id == "new" else object_id, action, await request.json())

    def page(request: Request):
        section = request.url.path.strip("/") or "overview"
        if section == "pipeline":
            section = "factory"
        return templates.TemplateResponse(request=request, name="center.html",
                                          context={**context(request, section), "section": section})

    for path in ("/requirements", "/factory", "/prompts", "/outbox", "/history"):
        app.add_api_route(path, page, methods=["GET"])
