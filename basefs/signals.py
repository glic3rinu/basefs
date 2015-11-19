def register(signal, method):
    try:
        registry[signal].append(method)
    except KeyError:
        registry[signal] = [method]


def send(signal, *args, **kwagrs):
    try:
        methods = registry[signal]
    except KeyError:
        return
    for method in methods:
        method(*args, **kwargs)


registry = {}
