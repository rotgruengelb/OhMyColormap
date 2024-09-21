import logging
import time

from typing import Callable, Any


def time_this(func: Callable) -> Callable:
    """
    A decorator that logs the time a function takes to execute.

    Args:
        func (Callable): The function to be timed.

    Returns:
        Callable: The wrapped function with timing functionality.
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.info(f"Function {func.__name__} took {end_time - start_time:.2f} seconds")
        return result

    return wrapper