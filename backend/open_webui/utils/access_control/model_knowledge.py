from __future__ import annotations

from copy import deepcopy

from open_webui.models.access_grants import AccessGrants
from open_webui.models.files import Files
from open_webui.models.groups import Groups
from open_webui.models.knowledge import Knowledges
from open_webui.models.notes import Notes
from open_webui.models.users import UserModel
from sqlalchemy.ext.asyncio import AsyncSession

# This flag exists only on the per-request model copy. It must never be persisted
# or returned by an API. It means that the caller may use the attachment through
# the already-authorized model's RAG pipeline, but has no direct read permission
# on the underlying knowledge object.
MODEL_RAG_ONLY_KEY = '_model_rag_only'


def is_model_rag_only(item: dict) -> bool:
    return item.get(MODEL_RAG_ONLY_KEY) is True


async def resolve_model_knowledge_for_inference(  # noqa: C901
    entries: list[dict] | None,
    user: UserModel,
    db: AsyncSession | None = None,
) -> list[dict]:
    """Resolve server-configured model knowledge for one chat request.

    A model attachment may be queried through RAG once the caller has passed the
    model access check. Direct Knowledge/File/Note APIs retain their independent
    access checks. Notes are excluded unless directly readable because the note
    retrieval path returns the entire note rather than bounded vector chunks.
    """
    if not isinstance(entries, list):
        return []

    resolved: list[dict] = []
    user_group_ids = None

    async def get_user_group_ids() -> set[str]:
        nonlocal user_group_ids
        if user_group_ids is None:
            user_group_ids = {group.id for group in await Groups.get_groups_by_member_id(user.id, db=db)}
        return user_group_ids

    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue

        entry_type = raw_entry.get('type')
        entry_id = raw_entry.get('id')
        if entry_type not in {'collection', 'file', 'note'} or not entry_id:
            continue

        entry = deepcopy(raw_entry)
        entry.pop(MODEL_RAG_ONLY_KEY, None)

        if user.role == 'admin':
            resolved.append(entry)
            continue

        if entry_type == 'collection':
            knowledge = await Knowledges.get_knowledge_by_id(entry_id, db=db)
            if not knowledge:
                continue
            has_direct_access = knowledge.user_id == user.id or await AccessGrants.has_access(
                user_id=user.id,
                resource_type='knowledge',
                resource_id=knowledge.id,
                permission='read',
                user_group_ids=await get_user_group_ids(),
                db=db,
            )
        elif entry_type == 'file':
            from open_webui.utils.access_control.files import has_access_to_file

            if not await Files.get_file_by_id(entry_id, db=db):
                continue
            has_direct_access = await has_access_to_file(
                entry_id,
                'read',
                user,
                db=db,
                user_group_ids=await get_user_group_ids(),
            )
        else:
            note = await Notes.get_note_by_id(entry_id, db=db)
            if not note:
                continue
            has_direct_access = note.user_id == user.id or await AccessGrants.has_access(
                user_id=user.id,
                resource_type='note',
                resource_id=note.id,
                permission='read',
                user_group_ids=await get_user_group_ids(),
                db=db,
            )
            if not has_direct_access:
                continue

        if not has_direct_access:
            entry[MODEL_RAG_ONLY_KEY] = True
        resolved.append(entry)

    return resolved
