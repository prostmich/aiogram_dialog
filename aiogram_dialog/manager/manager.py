from typing import Optional, Any, Dict, Union

from aiogram.dispatcher.filters.state import State
from aiogram.dispatcher.storage import FSMContextProxy
from aiogram.types import CallbackQuery, Message

from .intent import Data, Intent
from .protocols import DialogRegistryProto, DialogManagerProto
from .stack import DialogStack
from ..data import DialogContext, reset_dialog_contexts

ChatEvent = Union[CallbackQuery, Message]


async def remove_kbd_safe(event: ChatEvent, proxy: FSMContextProxy):
    if isinstance(event, CallbackQuery):
        await event.message.edit_reply_markup()
    else:
        stub_context = DialogContext(proxy, "", None)
        last_message_id = stub_context.last_message_id
        if last_message_id:
            await event.bot.edit_message_reply_markup(event.chat.id, last_message_id)


class DialogManager(DialogManagerProto):
    def __init__(
            self, event: ChatEvent, stack: DialogStack,
            proxy: FSMContextProxy, registry: DialogRegistryProto,
            data: Dict
    ):
        self.proxy = proxy
        self.stack = stack
        self.registry = registry
        self.event = event
        self.data = data
        self.context = self.load_context()

    async def start(self, state: State, data: Data = None, reset_stack: bool = False):
        if reset_stack:
            await remove_kbd_safe(self.event, self.proxy)
            reset_dialog_contexts(self.proxy)
        dialog = self.registry.find_dialog(state)
        self.stack.push(state.state, data)
        self.context = self.load_context()
        await dialog.start(self, state)

    async def done(self, result: Any = None, intent: Optional[Intent] = None):
        self.stack.pop(intent)
        self.context.clear()
        intent = self.current_intent()
        if intent:
            self.proxy.state = intent.name
        else:
            self.proxy.state = None
        dialog = self.dialog()
        self.context = self.load_context()
        if dialog:
            await dialog.process_result(result, self)
            await dialog.show(self)
        else:
            await remove_kbd_safe(self.event, self.proxy)

    async def close(self, intent: Intent):
        self.context.clear()
        self.stack.pop(intent)

    def current_intent(self) -> Intent:
        return self.stack.current()

    def dialog(self):
        current = self.current_intent()
        if not current:
            return None
        return self.registry.find_dialog(current.name)

    def load_context(self) -> Optional[DialogContext]:
        dialog = self.dialog()
        if not dialog:
            return None
        return DialogContext(self.proxy, dialog.states_group_name(), dialog.states_group())

    async def refresh(self):
        await self.registry.update_handler.notify(self.event)

    def switch_to(self, state):
        self.context.state = state
