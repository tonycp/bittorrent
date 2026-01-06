from bit_lib.models.message import Request


def create_hook(controller, command, func):
    def hook(**kwargs):
        return Request(controller, command, func, kwargs)

    return hook
