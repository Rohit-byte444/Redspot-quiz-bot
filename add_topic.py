from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

import config
from bot import db
import logging
from typing import Optional, Dict, Any
from .start_bot import main_menu_keyboard, welcome_message

logger = logging.getLogger(__name__)

# Router setup
add_topic_router = Router(name="add_topic")


class AddTopicStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()


SPONSOR_FOOTER = f" "

# Predefined messages
MESSAGES = {
    "enter_name": "✏️ لطفاً نام موضوع را وارد کنید:" + SPONSOR_FOOTER,
    "enter_description": "📝 لطفاً توضیحات موضوع را وارد کنید:" + SPONSOR_FOOTER,
    "name_empty": "⚠️ نام موضوع نمی‌تواند خالی باشد." + SPONSOR_FOOTER,
    "name_length": f"⚠️ طول نام موضوع باید بین {config.TOPIC_NAME_MIN_LENGTH} و {config.TOPIC_NAME_MAX_LENGTH} کاراکتر باشد." + SPONSOR_FOOTER,
    "name_exists": "⚠️ موضوعی با این نام قبلاً وجود دارد. لطفاً نام دیگری انتخاب کنید." + SPONSOR_FOOTER,
    "description_empty": "⚠️ توضیحات موضوع نمی‌تواند خالی باشد." + SPONSOR_FOOTER,
    "description_length": f"⚠️ طول توضیحات موضوع باید بین {config.TOPIC_DESCRIPTION_MIN_LENGTH} و {config.TOPIC_DESCRIPTION_MAX_LENGTH} کاراکتر باشد." + SPONSOR_FOOTER,
    "only_text": "⚠️ لطفاً فقط پیام متنی ارسال کنید." + SPONSOR_FOOTER,
    "success": """
✅ موضوع با موفقیت اضافه شد

🔖 نام: 
{name}

📄 توضیحات: 
{description}

🕒 تاریخ ایجاد: 
{created_at}

⚡ وضعیت فعال: 
{is_active}

🆔 شناسه موضوع: 
{topic_id}
""" + SPONSOR_FOOTER,
    "error": "❌ خطایی رخ داده است: {error}" + SPONSOR_FOOTER,
    "welcome_back": "👋 {full_name} عزیز، خوش آمدید!" + SPONSOR_FOOTER,
    
    # Keyboard button texts
    "btn_cancel": "❌ لغو",
}


# Helper functions
async def safe_edit_message(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:

    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            logger.debug("Message not modified, content is the same")
            return True
        else:
            logger.error(f"Error editing message: {e}")
            return False
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        return False


def get_cancel_keyboard() -> InlineKeyboardMarkup:

    kb = InlineKeyboardBuilder()
    kb.button(text=MESSAGES["btn_cancel"], callback_data="add_topic_cancel")
    return kb.as_markup()


@add_topic_router.message(Command("add_topic"), F.from_user.id == config.ADMIN_ID)
async def cmd_add_topic(message: Message, state: FSMContext) -> None:

    try:
        await state.set_state(AddTopicStates.waiting_for_name)

        await message.answer(
            text=MESSAGES["enter_name"],
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} initiated topic creation")
    except Exception as e:
        logger.error(f"Error starting add_topic: {e}")



@add_topic_router.callback_query(F.data == "add_topic_cancel")
async def cancel_add_topic(callback: CallbackQuery, state: FSMContext) -> None:
 
    await state.clear()
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        logger.debug("Could not delete message, it might be too old")

    try:
        await callback.message.answer(
            text=welcome_message.format(full_name=callback.from_user.full_name, bot_name=config.BOT_NAME),
            reply_markup=main_menu_keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        await callback.answer()
        logger.info(f"Admin {callback.from_user.id} cancelled topic creation")
    except Exception as e:
        logger.error(f"Error returning to main menu: {e}")



@add_topic_router.message(AddTopicStates.waiting_for_name, F.text)
async def process_topic_name(message: Message, state: FSMContext) -> None:
   
    topic_name = message.text.strip()

    try:
        if not topic_name:
            await message.answer(
                text=MESSAGES["name_empty"],
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return

        if len(topic_name) < config.TOPIC_NAME_MIN_LENGTH or len(topic_name) > config.TOPIC_NAME_MAX_LENGTH:
            await message.answer(
                text=MESSAGES["name_length"],
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return

        existing_topic = db.get_topic_by_name(topic_name)
        if existing_topic["status"] == "success":
            await message.answer(
                text=MESSAGES["name_exists"],
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return

        await state.update_data(topic_name=topic_name)
        await state.set_state(AddTopicStates.waiting_for_description)

        await message.answer(
            text=MESSAGES["enter_description"],
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Admin {message.from_user.id} entered topic name: {topic_name}")
    except Exception as e:
        logger.error(f"Error processing topic name: {e}")



@add_topic_router.message(AddTopicStates.waiting_for_name)
async def process_invalid_name_input(message: Message) -> None:
  
    await message.answer(
        text=MESSAGES["only_text"],
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    logger.warning(f"User {message.from_user.id} sent non-text message when name was expected")


@add_topic_router.message(AddTopicStates.waiting_for_description, F.text)
async def process_topic_description(message: Message, state: FSMContext) -> None:
   
    topic_description = message.text.strip()

    try:
        if not topic_description:
            await message.answer(
                text=MESSAGES["description_empty"],
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return

        if len(topic_description) < config.TOPIC_DESCRIPTION_MIN_LENGTH or len(
                topic_description) > config.TOPIC_DESCRIPTION_MAX_LENGTH:
            await message.answer(
                text=MESSAGES["description_length"],
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return

        data = await state.get_data()
        topic_name = data.get("topic_name")

        result = db.create_topic(topic_name=topic_name, topic_description=topic_description)

        if result["status"] == "success":
            success_message = MESSAGES["success"].format(
                name=result["topic"]["name"],
                description=result["topic"]["description"],
                created_at=result["topic"]["created_at"],
                is_active=result["topic"]["is_active"],
                topic_id=result["topic"]["topic_id"]
            )
            await message.answer(
                text=success_message,
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Admin {message.from_user.id} created topic: {topic_name} (ID: {result['topic']['topic_id']})")
        else:
            logger.error(f"Error creating topic: {result['message']}")
            await message.answer(
                text=MESSAGES["error"].format(error=result["message"]),
                parse_mode=ParseMode.HTML
            )

        await state.clear()
    except Exception as e:
        logger.error(f"Error processing topic description: {e}")
        await state.clear()


@add_topic_router.message(AddTopicStates.waiting_for_description)
async def process_invalid_description_input(message: Message) -> None:

    await message.answer(
        text=MESSAGES["only_text"],
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    logger.warning(f"User {message.from_user.id} sent non-text message when description was expected")
