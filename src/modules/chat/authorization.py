"""Authorize chat requests using token identity and project ownership."""
from fastapi import HTTPException, Request
from src.shared.project_access import get_auth_context, require_project_access


async def authorize_chat_request(request: Request):
    context = await get_auth_context(request)
    if context['auth_type'] == 'service':
        return
    if request.url.path.rstrip('/').endswith('/chat/migrate'):
        raise HTTPException(status_code=403, detail='Internal maintenance endpoint')
    data = {}
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and 'application/json' in request.headers.get('content-type', ''):
        try:
            data = await request.json()
        except ValueError:
            raise HTTPException(status_code=400, detail='Invalid JSON')
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail='Expected an object')
    user = str(context['user'].get('user_id') or context['user'].get('id'))
    for claimed in (request.query_params.get('user_id'), data.get('user_id')):
        if claimed is not None and str(claimed) != user:
            raise HTTPException(status_code=403, detail='User identity does not match token')
    project = request.path_params.get('project_id') or request.query_params.get('project_id') or data.get('project_id')
    if data.get('chat_history_id'):
        from src.database import get_db
        from .models import ChatHistory
        sessions = get_db()
        try:
            row = next(sessions).get(ChatHistory, data['chat_history_id'])
            if not row or str(row.user_id) != user:
                raise HTTPException(status_code=404, detail='Conversation not found')
            project = row.project_id
        finally:
            sessions.close()
    if not project:
        # Unscoped maintenance operations are internal-service only.
        raise HTTPException(status_code=403, detail='Project-scoped access required')
    await require_project_access(request, str(project), auth_context=context)
    if data:
        # request.json() caches this object; downstream handlers use verified identity.
        data['user_id'] = user
