MAX_EXECUTOR_WORKERS = 64


@dataclasses.dataclass
class RuntimeConfig:

    config_dir: str
    skip_pip: bool = False
    safe_mode: bool = False

    verbose: bool = False

    log_rotate_days: Optional[int] = None
    log_file: Optional[str] = None
    log_no_color: bool = False

    debug: bool = False
    open_ui: bool = False

if sys.platform == "win32" and sys.version_info[:2] < (3, 8):
    PolicyBase = asyncio.WindowsProactorEventLoopPolicy
else:
    PolicyBase = asyncio.DefaultEventLoopPolicy


class HassEventLoopPolicy(PolicyBase):
    """Event loop policy for server."""

    def __init__(self, debug: bool) -> None:
        """Init the event loop policy."""
        super().__init__()
        self.debug = debug

    @property
    def loop_name(self) -> str:
        """Return name of the loop."""
        return self._loop_factory.__name__  
    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop."""
        loop: asyncio.AbstractEventLoop = super().new_event_loop()
        loop.set_exception_handler(_async_loop_exception_handler)
        if self.debug:
            loop.set_debug(True)

        executor = ThreadPoolExecutor(
            thread_name_prefix="SyncWorker", max_workers=MAX_EXECUTOR_WORKERS
        )
        loop.set_default_executor(executor)
        loop.set_default_executor = warn_use(
            loop.set_default_executor, "sets default executor on the event loop"
        )

        orig_close = loop.close

        def close() -> None:
            executor.shutdown(wait=True)
            orig_close()

        loop.close = close 

        return loop


@callback
def _async_loop_exception_handler(_: Any, context: Dict) -> None:
    """Handle all exception inside the core loop."""
    kwargs = {}
    exception = context.get("exception")
    if exception:
        kwargs["exc_info"] = (type(exception), exception, exception.__traceback__)

    logging.getLogger(__package__).error(
        "Error doing job: %s", context["message"], **kwargs
    )


async def setup_and_run_hass(runtime_config: RuntimeConfig) -> int:
    """Set up server and run."""
    hass = await bootstrap.async_setup_hass(runtime_config)

    if hass is None:
        return 1

    return await hass.async_run()


def run(runtime_config: RuntimeConfig) -> int:
    """Run server."""
    asyncio.set_event_loop_policy(HassEventLoopPolicy(runtime_config.debug))
    return asyncio.run(setup_and_run_hass(runtime_config))
