from collections import defaultdict


class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, event: str, handler):
        if handler not in self._handlers[event]:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler):
        self._handlers[event] = [h for h in self._handlers[event] if h != handler]

    def publish(self, event: str, data=None):
        for handler in list(self._handlers[event]):
            try:
                handler(data)
            except Exception as e:
                print(f"[事件总线] {event} 处理器异常: {e}")


bus = EventBus()
