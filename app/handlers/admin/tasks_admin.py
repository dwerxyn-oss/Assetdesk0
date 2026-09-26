from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ADMIN_PAGE_SIZE,
    CHANNEL_TASK_TYPES,
    TASK_CHANNEL_OPEN,
    TASK_CHANNEL_SUBSCRIPTION,
    TASK_CUSTOM,
    TASK_PARTNER,
    TASK_REFERRAL,
)
from app.filters import AdminFilter, PrivateFilter
from app.keyboards.admin import task_card_kb, task_list_kb, task_type_kb
from app.keyboards.callbacks import AdminCB
from app.keyboards.common import back, kb
from app.middlewares.context import PLAIN_TEXT
from app.services.tasks import (
    completion_count,
    create_task,
    delete_task,
    get_task,
    list_all,
    update_task_fields,
)
from app.states.flows import AdminTaskStates
from app.texts.admin import task_card
from app.utils.parsing import parse_channel, parse_non_negative_int, parse_positive_int
from app.utils.ui import show_screen

router = Router(name="admin-tasks")
router.message.filter(PrivateFilter(), AdminFilter())
router.callback_query.filter(PrivateFilter(), AdminFilter())

_TYPES = {
    "typ_sub": TASK_CHANNEL_SUBSCRIPTION,
    "typ_open": TASK_CHANNEL_OPEN,
    "typ_custom": TASK_CUSTOM,
    "typ_ref": TASK_REFERRAL,
    "typ_partner": TASK_PARTNER,
}


async def _show_task(event, session: AsyncSession, task_id: int) -> None:
    task = await get_task(session, task_id)
    if task is None:
        if isinstance(event, CallbackQuery):
            await event.answer("Задание не найдено.", show_alert=True)
        return
    done = await completion_count(session, task.id)
    await show_screen(event, task_card(task, done), task_card_kb(task))


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "list")))
async def task_list(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    tasks = await list_all(session)
    page = max(callback_data.page, 0)
    has_next = (page + 1) * ADMIN_PAGE_SIZE < len(tasks)
    if tasks and page * ADMIN_PAGE_SIZE >= len(tasks):
        page = 0
        has_next = ADMIN_PAGE_SIZE < len(tasks)
    await show_screen(query, "<b>Задания</b>", task_list_kb(tasks, page, has_next))


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "view")))
async def task_view(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    await _show_task(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "new")))
async def task_new(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminTaskStates.title)
    await show_screen(
        query,
        "Название задания.",
        kb([back(AdminCB(section="task", action="list"))]),
    )


@router.message(AdminTaskStates.title, PLAIN_TEXT)
async def task_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 150:
        await message.answer("Название нужно, до 150 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminTaskStates.description)
    await message.answer("Описание. Если его нет, отправьте «-».")


@router.message(AdminTaskStates.description, PLAIN_TEXT)
async def task_description(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    await state.update_data(description="" if raw == "-" else raw[:1000])
    await state.set_state(AdminTaskStates.reward)
    await message.answer("Награда в целых ⭐.")


@router.message(AdminTaskStates.reward, PLAIN_TEXT)
async def task_reward(message: Message, state: FSMContext) -> None:
    reward = parse_non_negative_int(message.text or "")
    if reward is None or reward > 1_000_000:
        await message.answer("Нужно целое число от 0.")
        return
    await state.update_data(reward=reward)
    await state.set_state(AdminTaskStates.task_type)
    await message.answer("Тип задания.", reply_markup=task_type_kb())


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action.startswith("typ_"))))
async def task_type(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    if await state.get_state() != AdminTaskStates.task_type.state:
        await query.answer("Сначала начните создание задания.", show_alert=True)
        return
    task_type_name = _TYPES.get(callback_data.action)
    if task_type_name is None:
        await query.answer("Некорректное действие", show_alert=True)
        return
    await state.update_data(task_type=task_type_name)
    await state.set_state(AdminTaskStates.extra)
    if task_type_name in CHANNEL_TASK_TYPES:
        prompt = "Укажите @channel или числовой id канала. Бот проверит подписку."
    elif task_type_name == TASK_REFERRAL:
        prompt = "Сколько приглашённых должны выполнить задание? Введите число."
    elif task_type_name == TASK_CUSTOM:
        prompt = "Условие для пользователя. Если не нужно, отправьте «-». Награда придёт через 1 минуту."
    else:
        prompt = "Ссылка, если нужна. Если нет, отправьте «-». Награда придёт через 1 минуту."
    await show_screen(query, prompt, kb([back(AdminCB(section="task", action="list"))]))


@router.message(AdminTaskStates.extra, PLAIN_TEXT)
async def task_extra(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    kind = data.get("task_type")
    text = (message.text or "").strip()
    payload = {"target": "", "channel_username": None, "channel_id": None}
    if kind in CHANNEL_TASK_TYPES:
        parsed = parse_channel(text)
        if parsed is None or parsed == (None, None):
            await message.answer("Нужен @username канала или числовой id.")
            return
        payload["channel_username"], payload["channel_id"] = parsed
    elif kind == TASK_REFERRAL:
        number = parse_positive_int(text)
        if number is None:
            await message.answer("Введите число больше нуля.")
            return
        payload["target"] = str(number)
    else:
        payload["target"] = "" if text == "-" else text[:300]
    await state.update_data(**payload)
    await state.set_state(AdminTaskStates.max_completions)
    await message.answer("Лимит выполнений. 0 — без лимита.")


@router.message(AdminTaskStates.max_completions, PLAIN_TEXT)
async def task_max(message: Message, session: AsyncSession, state: FSMContext) -> None:
    limit = parse_non_negative_int(message.text or "")
    if limit is None:
        await message.answer("Введите 0 или число больше нуля.")
        return
    data = await state.get_data()
    await state.clear()
    created = await create_task(
        session,
        title=data["title"],
        description=data.get("description", ""),
        reward=int(data["reward"]),
        task_type=data["task_type"],
        target=data.get("target", ""),
        channel_username=data.get("channel_username"),
        channel_id=data.get("channel_id"),
        max_completions=limit,
    )
    if isinstance(created, str):
        await message.answer("Не получилось создать задание.")
        return
    await _show_task(message, session, created.id)


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action.startswith("ed_"))))
async def task_edit(query: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    field = callback_data.action.removeprefix("ed_")
    prompts = {
        "title": "Новое название.",
        "desc": "Новое описание. «-» очистит его.",
        "reward": "Новая награда, целое число.",
        "extra": "Новый канал или условие.",
        "max": "Новый лимит выполнений. 0 — без лимита.",
    }
    if field not in prompts:
        await query.answer("Некорректное действие", show_alert=True)
        return
    await state.set_state(AdminTaskStates.edit_value)
    await state.set_data({"task_id": callback_data.item_id, "field": field})
    await show_screen(
        query,
        prompts[field],
        kb([back(AdminCB(section="task", action="view", item_id=callback_data.item_id))]),
    )


@router.message(AdminTaskStates.edit_value, PLAIN_TEXT)
async def task_edit_value(message: Message, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    task = await get_task(session, int(data["task_id"]))
    if task is None:
        await state.clear()
        await message.answer("Задание не найдено.")
        return
    field = data["field"]
    text = (message.text or "").strip()
    changes: dict[str, object] = {}
    if field == "title":
        if not text or len(text) > 150:
            await message.answer("Название нужно, до 150 символов.")
            return
        changes["title"] = text
    elif field == "desc":
        changes["description"] = "" if text == "-" else text[:1000]
    elif field == "reward":
        reward = parse_non_negative_int(text)
        if reward is None:
            await message.answer("Нужно целое число от 0.")
            return
        changes["reward"] = reward
    elif field == "max":
        limit = parse_non_negative_int(text)
        if limit is None:
            await message.answer("Нужно целое число от 0.")
            return
        changes["max_completions"] = limit
    elif field == "extra":
        if task.task_type in CHANNEL_TASK_TYPES:
            parsed = parse_channel(text)
            if parsed is None or parsed == (None, None):
                await message.answer("Нужен @username канала или числовой id.")
                return
            changes["channel_username"], changes["channel_id"] = parsed
        elif task.task_type == TASK_REFERRAL:
            number = parse_positive_int(text)
            if number is None:
                await message.answer("Введите число больше нуля.")
                return
            changes["target"] = str(number)
        else:
            changes["target"] = "" if text == "-" else text[:300]
    code = await update_task_fields(session, task.id, **changes)
    await state.clear()
    if code != "ok":
        await message.answer("Не получилось сохранить задание.")
        return
    await _show_task(message, session, task.id)


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "toggle")))
async def task_toggle(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    task = await get_task(session, callback_data.item_id)
    if task is None:
        await query.answer("Задание не найдено.", show_alert=True)
        return
    if task.archived:
        await query.answer("Сначала верните задание из архива.", show_alert=True)
        return
    code = await update_task_fields(session, task.id, active=not task.active)
    if code != "ok":
        await query.answer("Не получилось изменить задание.", show_alert=True)
        return
    await _show_task(query, session, task.id)


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "archive")))
async def task_archive(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    code = await update_task_fields(session, callback_data.item_id, archived=True, active=False)
    if code != "ok":
        await query.answer("Задание не найдено.", show_alert=True)
        return
    await _show_task(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "unarchive")))
async def task_unarchive(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    code = await update_task_fields(session, callback_data.item_id, archived=False, active=False)
    if code != "ok":
        await query.answer("Задание не найдено.", show_alert=True)
        return
    await _show_task(query, session, callback_data.item_id)


@router.callback_query(AdminCB.filter((F.section == "task") & (F.action == "delete")))
async def task_delete(query: CallbackQuery, callback_data: AdminCB, session: AsyncSession) -> None:
    code = await delete_task(session, callback_data.item_id)
    if code == "has_completions":
        await query.answer("Есть выполнения. Отправьте задание в архив.", show_alert=True)
        return
    if code != "ok":
        await query.answer("Задание не найдено.", show_alert=True)
        return
    tasks = await list_all(session)
    await show_screen(query, "Задание удалено.\n\n<b>Задания</b>", task_list_kb(tasks, 0, ADMIN_PAGE_SIZE < len(tasks)))
