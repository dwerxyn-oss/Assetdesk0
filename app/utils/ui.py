from __future__ import annotations

import logging
from pathlib import Path

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    LinkPreviewOptions,
    Message,
)

_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
BANNERS = {
    "menu": _ASSET_DIR / "menu.jpg",
    "earn": _ASSET_DIR / "earn.jpg",
    "sell": _ASSET_DIR / "sell.jpg",
}

logger = logging.getLogger(__name__)

PREVIEW_OFF = LinkPreviewOptions(is_disabled=True)
_file_ids: dict[str, str] = {}


def _source(key: str) -> str | FSInputFile:
    cached = _file_ids.get(key)
    if cached:
        return cached
    path = BANNERS[key]
    if not path.is_file():
        raise FileNotFoundError(path)
    return FSInputFile(path)


def _remember(key: str, result: Message | bool) -> None:
    if isinstance(result, Message) and result.photo:
        _file_ids[key] = result.photo[-1].file_id


async def show_screen(
    event: Message | CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
    *,
    alert: str | None = None,
    photo: str | None = None,
) -> None:
    if isinstance(event, CallbackQuery):
        if alert:
            await event.answer(alert, show_alert=True)
        else:
            await event.answer()
        if event.message is None:
            return
        await _edit(event.message, text, markup, photo)
        return
    await _send(event, text, markup, photo)


async def _edit(
    message: Message,
    text: str,
    markup: InlineKeyboardMarkup | None,
    photo: str | None,
) -> None:
    if photo:
        await _edit_photo(message, photo, text, markup)
        return
    if message.photo:
        await _replace_text(message, text, markup)
        return
    try:
        await message.edit_text(text, reply_markup=markup, link_preview_options=PREVIEW_OFF)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        logger.info("edit failed, sending a new message: %s", exc.__class__.__name__)
        await message.answer(text, reply_markup=markup, link_preview_options=PREVIEW_OFF)


async def _edit_photo(
    message: Message,
    key: str,
    text: str,
    markup: InlineKeyboardMarkup | None,
) -> None:
    if message.photo:
        try:
            result = await message.edit_media(
                InputMediaPhoto(media=_source(key), caption=text, parse_mode=ParseMode.HTML),
                reply_markup=markup,
            )
            _remember(key, result)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            logger.info("photo edit failed, sending a new message: %s", exc.__class__.__name__)
        except FileNotFoundError:
            logger.exception("banner missing key=%s", key)
            await _replace_text(message, text, markup)
            return
    await _replace_photo(message, key, text, markup)


async def _replace_photo(
    message: Message,
    key: str,
    text: str,
    markup: InlineKeyboardMarkup | None,
) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        logger.info("previous screen was not deleted")
    try:
        sent = await message.answer_photo(_source(key), caption=text, reply_markup=markup)
    except FileNotFoundError:
        logger.exception("banner missing key=%s", key)
        await message.answer(text, reply_markup=markup, link_preview_options=PREVIEW_OFF)
        return
    _remember(key, sent)


async def _replace_text(message: Message, text: str, markup: InlineKeyboardMarkup | None) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        logger.info("previous screen was not deleted")
    await message.answer(text, reply_markup=markup, link_preview_options=PREVIEW_OFF)


async def _send(
    message: Message,
    text: str,
    markup: InlineKeyboardMarkup | None,
    photo: str | None,
) -> None:
    if not photo:
        await message.answer(text, reply_markup=markup, link_preview_options=PREVIEW_OFF)
        return
    try:
        sent = await message.answer_photo(_source(photo), caption=text, reply_markup=markup)
    except FileNotFoundError:
        logger.exception("banner missing key=%s", photo)
        await message.answer(text, reply_markup=markup, link_preview_options=PREVIEW_OFF)
        return
    _remember(photo, sent)
