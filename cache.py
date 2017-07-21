"""
Provide cache decorators.
"""
import hashlib
import logging
import os
import pickle
import threading

_LOCK = threading.Lock()


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
    if var_p is None:
        logging.debug("Cache disabled, running function.")
        return var_fn()

    try:
        with open(var_p, 'rb') as var_fs:
            var = pickle.load(var_fs)

        if var_check(var):
            logging.debug(
                "%s cached, variable loaded.", var_fn.__name__)
            if hook is not None:
                hook()
        else:
            raise FileNotFoundError

    except FileNotFoundError:
        logging.debug("%s cache miss, running.", var_fn.__name__)
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
        var_p = os.path.join("pickle.d", func.__name__ + ".p")

    return pickle_cache_witness(func, var_p, lambda _: True, hook=hook)


def cache_func_and_arg(func):
    def get_hash(var):
        return hashlib.md5(str(var).encode('utf8')).hexdigest()

    def new_func(arg):
        var_p = os.path.join("pickle.d",
                             func.__name__ + "_" + get_hash(arg) + ".p")
        if os.path.exists(var_p):
            with _LOCK:
                with open(var_p, 'rb') as var_fs:
                    return pickle.load(var_fs)
        else:
            res = func(arg)
            with _LOCK:
                with open(var_p, 'wb') as var_fs:
                    pickle.dump(res, var_fs)
            return res
    return new_func
