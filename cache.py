import logging
import pickle

_activate_cache = True


def set_pickle_cache(activate):
    global _activate_cache
    _activate_cache = activate


def pickle_cache_witness(var_fn, var_p, var_check, hook=None):
    """Cache the result of var_fn in var_p (fn of pickle file)

    Args:
        var_fn: the function to compute var
        var_p: the file path of the pickle file caching var
        var_check: a predicate such that if var_check(var), don't recompute
        hook: function to call when loading the cache (for side effects)

    Returns:
        the result of var_fn, from the cache if var_check(var_cached).
    """
    if not _activate_cache or var_p is None:
        logging.debug("Cache disabled, running function.")
        return var_fn()

    try:
        with open(var_p, 'rb') as f:
            var = pickle.load(f)

        if var_check(var):
            logging.debug(
                "{} cached, variable loaded.".format(var_fn.__name__))
            if hook is not None:
                hook()
        else:
            raise FileNotFoundError

    except FileNotFoundError:
        logging.debug("{} cache miss, running.".format(var_fn.__name__))
        var = var_fn()
        pickle.dump(var, open(var_p, 'wb'), protocol=pickle.HIGHEST_PROTOCOL)

    return var


def pickle_cache(var_fn, var_p, length):
    def var_check(var):
        return len(var) == length

    return pickle_cache_witness(var_fn, var_p, var_check)


def pickle_cache_witness_dec(var_p, var_check, hook=None):
    def decorate(func):
        def dec_func():
            return pickle_cache_witness(func, var_p, var_check, hook=hook)
        return dec_func
    return decorate


def always_cache(func, var_p=None, hook=None):
    if var_p is None:
        var_p = "pickle.d/" + func.__name__ + ".p"
    return pickle_cache_witness(func, var_p, (lambda _: True), hook=hook)
