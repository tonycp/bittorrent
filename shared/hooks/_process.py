from shared.proto import DataSerialize as p


def create_hook(controller, command, func):
    def hook(**kwargs):
        message = p.create_message(controller, command, func, kwargs)
        return p.encode_message(message)

    return hook
