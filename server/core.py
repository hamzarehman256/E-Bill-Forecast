block_async_io.enable()
fix_threading_exception_logging()

T = TypeVar("T")
_UNDEF: dict = {} 
CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)
CALLBACK_TYPE = Callable[[], None]

CORE_STORAGE_KEY = "core.config"
CORE_STORAGE_VERSION = 1

DOMAIN = "homeassistant"

BLOCK_LOG_TIMEOUT = 60

SERVICE_CALL_LIMIT = 10

SOURCE_DISCOVERED = "discovered"
SOURCE_STORAGE = "storage"
SOURCE_YAML = "yaml"

TIMEOUT_EVENT_START = 15

_LOGGER = logging.getLogger(__name__)


def split_entity_id(entity_id: str) -> List[str]:
    """Split a state entity_id into domain, object_id."""
    return entity_id.split(".", 1)


VALID_ENTITY_ID = re.compile(r"^(?!.+__)(?!_)[\da-z_]+(?<!_)\.(?!_)[\da-z_]+(?<!_)$")


def valid_entity_id(entity_id: str) -> bool:
    """Test if an entity ID is a valid format.

    Format: <domain>.<entity> where both are slugs.
    """
    return VALID_ENTITY_ID.match(entity_id) is not None


def valid_state(state: str) -> bool:
    """Test if a state is valid."""
    return len(state) < 256


def callback(func: CALLABLE_T) -> CALLABLE_T:
    """Annotation to mark method as safe to call from within the event loop."""
    setattr(func, "_hass_callback", True)
    return func


def is_callback(func: Callable[..., Any]) -> bool:
    """Check if function is safe to be called in the event loop."""
    return getattr(func, "_hass_callback", False) is True


@enum.unique
class HassJobType(enum.Enum):
    """Represent a job type."""

    Coroutinefunction = 1
    Callback = 2
    Executor = 3


class HassJob:
    """Represent a job to be run later.

    We check the callable type in advance
    so we can avoid checking it every time
    we run the job.
    """

    __slots__ = ("job_type", "target")

    def __init__(self, target: Callable):
        """Create a job object."""
        if asyncio.iscoroutine(target):
            raise ValueError("Coroutine not allowed to be passed to HassJob")

        self.target = target
        self.job_type = _get_callable_job_type(target)

    def __repr__(self) -> str:
        """Return the job."""
        return f"<Job {self.job_type} {self.target}>"


def _get_callable_job_type(target: Callable) -> HassJobType:
    """Determine the job type from the callable."""
    check_target = target
    while isinstance(check_target, functools.partial):
        check_target = check_target.func

    if asyncio.iscoroutinefunction(check_target):
        return HassJobType.Coroutinefunction
    if is_callback(check_target):
        return HassJobType.Callback
    return HassJobType.Executor


class CoreState(enum.Enum):
    """Represent the current state of Home Assistant."""

    not_running = "NOT_RUNNING"
    starting = "STARTING"
    running = "RUNNING"
    stopping = "STOPPING"
    final_write = "FINAL_WRITE"
    stopped = "STOPPED"

    def __str__(self) -> str:
        """Return the event."""
        return self.value 


class HomeAssistant:
    """Root object of the Home Assistant home automation."""

    auth: "AuthManager"
    http: "HomeAssistantHTTP" = None  
    config_entries: "ConfigEntries" = None

    def __init__(self) -> None:
        """Initialize new Home Assistant object."""
        self.loop = asyncio.get_running_loop()
        self._pending_tasks: list = []
        self._track_task = True
        self.bus = EventBus(self)
        self.services = ServiceRegistry(self)
        self.states = StateMachine(self.bus, self.loop)
        self.config = Config(self)
        self.components = loader.Components(self)
        self.helpers = loader.Helpers(self)
        self.data: dict = {}
        self.state: CoreState = CoreState.not_running
        self.exit_code: int = 0
        self._stopped: Optional[asyncio.Event] = None
        self.timeout: TimeoutManager = TimeoutManager()

    @property
    def is_running(self) -> bool:
        """Return if Home Assistant is running."""
        return self.state in (CoreState.starting, CoreState.running)

    @property
    def is_stopping(self) -> bool:
        """Return if Home Assistant is stopping."""
        return self.state in (CoreState.stopping, CoreState.final_write)

    def start(self) -> int:
        """Start Home Assistant.

        Note: This function is only used for testing.
        For regular use, use "await hass.run()".
        """
        fire_coroutine_threadsafe(self.async_start(), self.loop)

        # Run forever
        # Block until stopped
        _LOGGER.info("Starting Home Assistant core loop")
        self.loop.run_forever()
        return self.exit_code

    async def async_run(self, *, attach_signals: bool = True) -> int:
        """Home Assistant main entry point.

        Start Home Assistant and block until stopped.

        This method is a coroutine.
        """
        if self.state != CoreState.not_running:
            raise RuntimeError("Home Assistant is already running")

        self._stopped = asyncio.Event()

        await self.async_start()
        if attach_signals:
            from homeassistant.helpers.signal import async_register_signal_handling

            async_register_signal_handling(self)

        await self._stopped.wait()
        return self.exit_code

    async def async_start(self) -> None:
        """Finalize startup from inside the event loop.

        This method is a coroutine.
        """
        _LOGGER.info("Starting Home Assistant")
        setattr(self.loop, "_thread_ident", threading.get_ident())

        self.state = CoreState.starting
        self.bus.async_fire(EVENT_CORE_CONFIG_UPDATE)
        self.bus.async_fire(EVENT_HOMEASSISTANT_START)

        try:
            self.async_stop_track_tasks()
            async with self.timeout.async_timeout(TIMEOUT_EVENT_START):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Something is blocking Home Assistant from wrapping up the "
                "start up phase. We're going to continue anyway. Please "
                "report the following info at http://bit.ly/2ogP58T : %s",
                ", ".join(self.config.components),
            )

        await asyncio.sleep(0)

        if self.state != CoreState.starting:
            _LOGGER.warning(
                "Home Assistant startup has been interrupted. "
                "Its state may be inconsistent"
            )
            return

        self.state = CoreState.running
        self.bus.async_fire(EVENT_CORE_CONFIG_UPDATE)
        self.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        _async_create_timer(self)

    def add_job(self, target: Callable[..., Any], *args: Any) -> None:
        """Add job to the executor pool.

        target: target to call.
        args: parameters for method to call.
        """
        if target is None:
            raise ValueError("Don't call add_job with None")
        self.loop.call_soon_threadsafe(self.async_add_job, target, *args)

    @callback
    def async_add_job(
        self, target: Callable[..., Any], *args: Any
    ) -> Optional[asyncio.Future]:
        """Add a job from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        if target is None:
            raise ValueError("Don't call async_add_job with None")

        if asyncio.iscoroutine(target):
            return self.async_create_task(cast(Coroutine, target))

        return self.async_add_hass_job(HassJob(target), *args)

    @callback
    def async_add_hass_job(
        self, hassjob: HassJob, *args: Any
    ) -> Optional[asyncio.Future]:
        """Add a HassJob from within the event loop.

        This method must be run in the event loop.
        hassjob: HassJob to call.
        args: parameters for method to call.
        """
        if hassjob.job_type == HassJobType.Coroutinefunction:
            task = self.loop.create_task(hassjob.target(*args))
        elif hassjob.job_type == HassJobType.Callback:
            self.loop.call_soon(hassjob.target, *args)
            return None
        else:
            task = self.loop.run_in_executor(
                None, hassjob.target, *args
            )

        if self._track_task:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_create_task(self, target: Coroutine) -> asyncio.tasks.Task:
        """Create a task from within the eventloop.

        This method must be run in the event loop.

        target: target to call.
        """
        task: asyncio.tasks.Task = self.loop.create_task(target)

        if self._track_task:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_add_executor_job(
        self, target: Callable[..., T], *args: Any
    ) -> Awaitable[T]:
        """Add an executor job from within the event loop."""
        task = self.loop.run_in_executor(None, target, *args)

        if self._track_task:
            self._pending_tasks.append(task)

        return task

    @callback
    def async_track_tasks(self) -> None:
        """Track tasks so you can wait for all tasks to be done."""
        self._track_task = True

    @callback
    def async_stop_track_tasks(self) -> None:
        """Stop track tasks so you can't wait for all tasks to be done."""
        self._track_task = False

    @callback
    def async_run_hass_job(
        self, hassjob: HassJob, *args: Any
    ) -> Optional[asyncio.Future]:
        """Run a HassJob from within the event loop.

        This method must be run in the event loop.

        hassjob: HassJob
        args: parameters for method to call.
        """
        if hassjob.job_type == HassJobType.Callback:
            hassjob.target(*args)
            return None

        return self.async_add_hass_job(hassjob, *args)

    @callback
    def async_run_job(
        self, target: Callable[..., Union[None, Awaitable]], *args: Any
    ) -> Optional[asyncio.Future]:
        """Run a job from within the event loop.

        This method must be run in the event loop.

        target: target to call.
        args: parameters for method to call.
        """
        if asyncio.iscoroutine(target):
            return self.async_create_task(cast(Coroutine, target))

        return self.async_run_hass_job(HassJob(target), *args)

    def block_till_done(self) -> None:
        """Block until all pending work is done."""
        asyncio.run_coroutine_threadsafe(
            self.async_block_till_done(), self.loop
        ).result()

    async def async_block_till_done(self) -> None:
        """Block until all pending work is done."""
        await asyncio.sleep(0)
        start_time: Optional[float] = None

        while self._pending_tasks:
            pending = [task for task in self._pending_tasks if not task.done()]
            self._pending_tasks.clear()
            if pending:
                await self._await_and_log_pending(pending)

                if start_time is None:
                    start_time = 0
                elif start_time == 0:
                    
                    start_time = monotonic()
                elif monotonic() - start_time > BLOCK_LOG_TIMEOUT:
                   
                    for task in pending:
                        _LOGGER.debug("Waiting for task: %s", task)
            else:
                await asyncio.sleep(0)

    async def _await_and_log_pending(self, pending: Iterable[Awaitable[Any]]) -> None:
        """Await and log tasks that take a long time."""
        wait_time = 0
        while pending:
            _, pending = await asyncio.wait(pending, timeout=BLOCK_LOG_TIMEOUT)
            if not pending:
                return
            wait_time += BLOCK_LOG_TIMEOUT
            for task in pending:
                _LOGGER.debug("Waited %s seconds for task: %s", wait_time, task)

    def stop(self) -> None:
        """Stop Home Assistant and shuts down all threads."""
        if self.state == CoreState.not_running:
            return
        fire_coroutine_threadsafe(self.async_stop(), self.loop)

    async def async_stop(self, exit_code: int = 0, *, force: bool = False) -> None:
        """Stop Home Assistant and shuts down all threads.

        The "force" flag commands async_stop to proceed regardless of
        Home Assistan't current state. You should not set this flag
        unless you're testing.

        This method is a coroutine.
        """
        if not force:
            
            if self.state == CoreState.not_running: 
                return
            if self.state in [CoreState.stopping, CoreState.final_write]:
                _LOGGER.info("async_stop called twice: ignored")
                return
            if self.state == CoreState.starting:
                _LOGGER.warning("async_stop called before startup is complete")

       
        self.state = CoreState.stopping
        self.async_track_tasks()
        self.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        try:
            async with self.timeout.async_timeout(120):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown stage 1 to complete, the shutdown will continue"
            )

       
        self.state = CoreState.final_write
        self.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
        try:
            async with self.timeout.async_timeout(60):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown stage 2 to complete, the shutdown will continue"
            )

        
        self.state = CoreState.not_running
        self.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
        try:
            async with self.timeout.async_timeout(30):
                await self.async_block_till_done()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timed out waiting for shutdown stage 3 to complete, the shutdown will continue"
            )

        self.exit_code = exit_code
        self.state = CoreState.stopped

        if self._stopped is not None:
            self._stopped.set()


@attr.s(slots=True, frozen=True)
class Context:
    """The context that triggered something."""

    user_id: str = attr.ib(default=None)
    parent_id: Optional[str] = attr.ib(default=None)
    id: str = attr.ib(factory=uuid_util.random_uuid_hex)

    def as_dict(self) -> dict:
        """Return a dictionary representation of the context."""
        return {"id": self.id, "parent_id": self.parent_id, "user_id": self.user_id}


class EventOrigin(enum.Enum):
    """Represent the origin of an event."""

    local = "LOCAL"
    remote = "REMOTE"

    def __str__(self) -> str:  
        """Return the event."""
        return self.value


class Event:
    """Representation of an event within the bus."""

    __slots__ = ["event_type", "data", "origin", "time_fired", "context"]

    def __init__(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        origin: EventOrigin = EventOrigin.local,
        time_fired: Optional[datetime.datetime] = None,
        context: Optional[Context] = None,
    ) -> None:
        """Initialize a new event."""
        self.event_type = event_type
        self.data = data or {}
        self.origin = origin
        self.time_fired = time_fired or dt_util.utcnow()
        self.context: Context = context or Context()

    def __hash__(self) -> int:
        """Make hashable."""
        return hash((self.event_type, self.context.id, self.time_fired))

    def as_dict(self) -> Dict:
        """Create a dict representation of this Event.

        Async friendly.
        """
        return {
            "event_type": self.event_type,
            "data": dict(self.data),
            "origin": str(self.origin.value),
            "time_fired": self.time_fired.isoformat(),
            "context": self.context.as_dict(),
        }

    def __repr__(self) -> str:
        """Return the representation."""

        if self.data:
            return f"<Event {self.event_type}[{str(self.origin)[0]}]: {util.repr_helper(self.data)}>"

        return f"<Event {self.event_type}[{str(self.origin)[0]}]>"

    def __eq__(self, other: Any) -> bool:
        """Return the comparison."""
        return ( 
            self.__class__ == other.__class__
            and self.event_type == other.event_type
            and self.data == other.data
            and self.origin == other.origin
            and self.time_fired == other.time_fired
            and self.context == other.context
        )


class EventBus:
    """Allow the firing of and listening for events."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new event bus."""
        self._listeners: Dict[str, List[HassJob]] = {}
        self._hass = hass

    @callback
    def async_listeners(self) -> Dict[str, int]:
        """Return dictionary with events and the number of listeners.

        This method must be run in the event loop.
        """
        return {key: len(self._listeners[key]) for key in self._listeners}

    @property
    def listeners(self) -> Dict[str, int]:
        """Return dictionary with events and the number of listeners."""
        return run_callback_threadsafe(self._hass.loop, self.async_listeners).result()

    def fire(
        self,
        event_type: str,
        event_data: Optional[Dict] = None,
        origin: EventOrigin = EventOrigin.local,
        context: Optional[Context] = None,
    ) -> None:
        """Fire an event."""
        self._hass.loop.call_soon_threadsafe(
            self.async_fire, event_type, event_data, origin, context
        )

    @callback
    def async_fire(
        self,
        event_type: str,
        event_data: Optional[Dict] = None,
        origin: EventOrigin = EventOrigin.local,
        context: Optional[Context] = None,
        time_fired: Optional[datetime.datetime] = None,
    ) -> None:
        """Fire an event.

        This method must be run in the event loop.
        """
        listeners = self._listeners.get(event_type, [])


        match_all_listeners = self._listeners.get(MATCH_ALL)
        if match_all_listeners is not None and event_type != EVENT_HOMEASSISTANT_CLOSE:
            listeners = match_all_listeners + listeners

        event = Event(event_type, event_data, origin, time_fired, context)

        if event_type != EVENT_TIME_CHANGED:
            _LOGGER.debug("Bus:Handling %s", event)

        if not listeners:
            return

        for job in listeners:
            self._hass.async_add_hass_job(job, event)

    def listen(self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen, event_type, listener
        ).result()

        def remove_listener() -> None:
            """Remove the listener."""
            run_callback_threadsafe(self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen(self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen for all events or events of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        This method must be run in the event loop.
        """
        return self._async_listen_job(event_type, HassJob(listener))

    @callback
    def _async_listen_job(self, event_type: str, hassjob: HassJob) -> CALLBACK_TYPE:
        self._listeners.setdefault(event_type, []).append(hassjob)

        def remove_listener() -> None:
            """Remove the listener."""
            self._async_remove_listener(event_type, hassjob)

        return remove_listener

    def listen_once(self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns function to unsubscribe the listener.
        """
        async_remove_listener = run_callback_threadsafe(
            self._hass.loop, self.async_listen_once, event_type, listener
        ).result()

        def remove_listener() -> None:
            """Remove the listener."""
            run_callback_threadsafe(self._hass.loop, async_remove_listener).result()

        return remove_listener

    @callback
    def async_listen_once(self, event_type: str, listener: Callable) -> CALLBACK_TYPE:
        """Listen once for event of a specific type.

        To listen to all events specify the constant ``MATCH_ALL``
        as event_type.

        Returns registered listener that can be used with remove_listener.

        This method must be run in the event loop.
        """
        job: Optional[HassJob] = None

        @callback
        def _onetime_listener(event: Event) -> None:
            """Remove listener from event bus and then fire listener."""
            nonlocal job
            if hasattr(_onetime_listener, "run"):
                return
           
            setattr(_onetime_listener, "run", True)
            assert job is not None
            self._async_remove_listener(event_type, job)
            self._hass.async_run_job(listener, event)

        job = HassJob(_onetime_listener)

        return self._async_listen_job(event_type, job)

    @callback
    def _async_remove_listener(self, event_type: str, hassjob: HassJob) -> None:
        """Remove a listener of a specific event_type.

        This method must be run in the event loop.
        """
        try:
            self._listeners[event_type].remove(hassjob)

            if not self._listeners[event_type]:
                self._listeners.pop(event_type)
        except (KeyError, ValueError):
           
            _LOGGER.exception("Unable to remove unknown job listener %s", hassjob)


class State:
    """Object to represent a state within the state machine.

    entity_id: the entity that is represented.
    state: the state of the entity
    attributes: extra information on entity and state
    last_changed: last time the state was changed, not the attributes.
    last_updated: last time this object was updated.
    context: Context in which it was created
    domain: Domain of this state.
    object_id: Object id of this state.
    """

    __slots__ = [
        "entity_id",
        "state",
        "attributes",
        "last_changed",
        "last_updated",
        "context",
        "domain",
        "object_id",
        "_as_dict",
    ]

    def __init__(
        self,
        entity_id: str,
        state: str,
        attributes: Optional[Mapping] = None,
        last_changed: Optional[datetime.datetime] = None,
        last_updated: Optional[datetime.datetime] = None,
        context: Optional[Context] = None,
        validate_entity_id: Optional[bool] = True,
    ) -> None:
        """Initialize a new state."""
        state = str(state)

        if validate_entity_id and not valid_entity_id(entity_id):
            raise InvalidEntityFormatError(
                f"Invalid entity id encountered: {entity_id}. "
                "Format should be <domain>.<object_id>"
            )

        if not valid_state(state):
            raise InvalidStateError(
                f"Invalid state encountered for entity id: {entity_id}. "
                "State max length is 255 characters."
            )

        self.entity_id = entity_id.lower()
        self.state = state
        self.attributes = MappingProxyType(attributes or {})
        self.last_updated = last_updated or dt_util.utcnow()
        self.last_changed = last_changed or self.last_updated
        self.context = context or Context()
        self.domain, self.object_id = split_entity_id(self.entity_id)
        self._as_dict: Optional[Dict[str, Collection[Any]]] = None

    @property
    def name(self) -> str:
        """Name of this state."""
        return self.attributes.get(ATTR_FRIENDLY_NAME) or self.object_id.replace(
            "_", " "
        )

    def as_dict(self) -> Dict:
        """Return a dict representation of the State.

        Async friendly.

        To be used for JSON serialization.
        Ensures: state == State.from_dict(state.as_dict())
        """
        if not self._as_dict:
            last_changed_isoformat = self.last_changed.isoformat()
            if self.last_changed == self.last_updated:
                last_updated_isoformat = last_changed_isoformat
            else:
                last_updated_isoformat = self.last_updated.isoformat()
            self._as_dict = {
                "entity_id": self.entity_id,
                "state": self.state,
                "attributes": dict(self.attributes),
                "last_changed": last_changed_isoformat,
                "last_updated": last_updated_isoformat,
                "context": self.context.as_dict(),
            }
        return self._as_dict

    @classmethod
    def from_dict(cls, json_dict: Dict) -> Any:
        """Initialize a state from a dict.

        Async friendly.

        Ensures: state == State.from_json_dict(state.to_json_dict())
        """
        if not (json_dict and "entity_id" in json_dict and "state" in json_dict):
            return None

        last_changed = json_dict.get("last_changed")

        if isinstance(last_changed, str):
            last_changed = dt_util.parse_datetime(last_changed)

        last_updated = json_dict.get("last_updated")

        if isinstance(last_updated, str):
            last_updated = dt_util.parse_datetime(last_updated)

        context = json_dict.get("context")
        if context:
            context = Context(id=context.get("id"), user_id=context.get("user_id"))

        return cls(
            json_dict["entity_id"],
            json_dict["state"],
            json_dict.get("attributes"),
            last_changed,
            last_updated,
            context,
        )

    def __eq__(self, other: Any) -> bool:
        """Return the comparison of the state."""
        return ( 
            self.__class__ == other.__class__
            and self.entity_id == other.entity_id
            and self.state == other.state
            and self.attributes == other.attributes
            and self.context == other.context
        )

    def __repr__(self) -> str:
        """Return the representation of the states."""
        attrs = f"; {util.repr_helper(self.attributes)}" if self.attributes else ""

        return (
            f"<state {self.entity_id}={self.state}{attrs}"
            f" @ {dt_util.as_local(self.last_changed).isoformat()}>"
        )


class StateMachine:
    """Helper class that tracks the state of different entities."""

    def __init__(self, bus: EventBus, loop: asyncio.events.AbstractEventLoop) -> None:
        """Initialize state machine."""
        self._states: Dict[str, State] = {}
        self._reservations: Set[str] = set()
        self._bus = bus
        self._loop = loop

    def entity_ids(self, domain_filter: Optional[str] = None) -> List[str]:
        """List of entity ids that are being tracked."""
        future = run_callback_threadsafe(
            self._loop, self.async_entity_ids, domain_filter
        )
        return future.result()

    @callback
    def async_entity_ids(
        self, domain_filter: Optional[Union[str, Iterable]] = None
    ) -> List[str]:
        """List of entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return list(self._states)

        if isinstance(domain_filter, str):
            domain_filter = (domain_filter.lower(),)

        return [
            state.entity_id
            for state in self._states.values()
            if state.domain in domain_filter
        ]

    @callback
    def async_entity_ids_count(
        self, domain_filter: Optional[Union[str, Iterable]] = None
    ) -> int:
        """Count the entity ids that are being tracked.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return len(self._states)

        if isinstance(domain_filter, str):
            domain_filter = (domain_filter.lower(),)

        return len(
            [None for state in self._states.values() if state.domain in domain_filter]
        )

    def all(self, domain_filter: Optional[Union[str, Iterable]] = None) -> List[State]:
        """Create a list of all states."""
        return run_callback_threadsafe(
            self._loop, self.async_all, domain_filter
        ).result()

    @callback
    def async_all(
        self, domain_filter: Optional[Union[str, Iterable]] = None
    ) -> List[State]:
        """Create a list of all states matching the filter.

        This method must be run in the event loop.
        """
        if domain_filter is None:
            return list(self._states.values())

        if isinstance(domain_filter, str):
            domain_filter = (domain_filter.lower(),)

        return [
            state for state in self._states.values() if state.domain in domain_filter
        ]

    def get(self, entity_id: str) -> Optional[State]:
        """Retrieve state of entity_id or None if not found.

        Async friendly.
        """
        return self._states.get(entity_id.lower())

    def is_state(self, entity_id: str, state: str) -> bool:
        """Test if entity exists and is in specified state.

        Async friendly.
        """
        state_obj = self.get(entity_id)
        return state_obj is not None and state_obj.state == state

    def remove(self, entity_id: str) -> bool:
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.
        """
        return run_callback_threadsafe(
            self._loop, self.async_remove, entity_id
        ).result()

    @callback
    def async_remove(self, entity_id: str, context: Optional[Context] = None) -> bool:
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.

        This method must be run in the event loop.
        """
        entity_id = entity_id.lower()
        old_state = self._states.pop(entity_id, None)

        if entity_id in self._reservations:
            self._reservations.remove(entity_id)

        if old_state is None:
            return False

        self._bus.async_fire(
            EVENT_STATE_CHANGED,
            {"entity_id": entity_id, "old_state": old_state, "new_state": None},
            EventOrigin.local,
            context=context,
        )
        return True

    def set(
        self,
        entity_id: str,
        new_state: str,
        attributes: Optional[Dict] = None,
        force_update: bool = False,
        context: Optional[Context] = None,
    ) -> None:
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.
        """
        run_callback_threadsafe(
            self._loop,
            self.async_set,
            entity_id,
            new_state,
            attributes,
            force_update,
            context,
        ).result()

    @callback
    def async_reserve(self, entity_id: str) -> None:
        """Reserve a state in the state machine for an entity being added.

        This must not fire an event when the state is reserved.

        This avoids a race condition where multiple entities with the same
        entity_id are added.
        """
        entity_id = entity_id.lower()
        if entity_id in self._states or entity_id in self._reservations:
            raise HomeAssistantError(
                "async_reserve must not be called once the state is in the state machine."
            )

        self._reservations.add(entity_id)

    @callback
    def async_available(self, entity_id: str) -> bool:
        """Check to see if an entity_id is available to be used."""
        entity_id = entity_id.lower()
        return entity_id not in self._states and entity_id not in self._reservations

    @callback
    def async_set(
        self,
        entity_id: str,
        new_state: str,
        attributes: Optional[Dict] = None,
        force_update: bool = False,
        context: Optional[Context] = None,
    ) -> None:
        """Set the state of an entity, add entity if it does not exist.

        Attributes is an optional dict to specify attributes of this state.

        If you just update the attributes and not the state, last changed will
        not be affected.

        This method must be run in the event loop.
        """
        entity_id = entity_id.lower()
        new_state = str(new_state)
        attributes = attributes or {}
        old_state = self._states.get(entity_id)
        if old_state is None:
            same_state = False
            same_attr = False
            last_changed = None
        else:
            same_state = old_state.state == new_state and not force_update
            same_attr = old_state.attributes == MappingProxyType(attributes)
            last_changed = old_state.last_changed if same_state else None

        if same_state and same_attr:
            return

        if context is None:
            context = Context()

        now = dt_util.utcnow()

        state = State(
            entity_id,
            new_state,
            attributes,
            last_changed,
            now,
            context,
            old_state is None,
        )
        self._states[entity_id] = state
        self._bus.async_fire(
            EVENT_STATE_CHANGED,
            {"entity_id": entity_id, "old_state": old_state, "new_state": state},
            EventOrigin.local,
            context,
            time_fired=now,
        )


class Service:
    """Representation of a callable service."""

    __slots__ = ["job", "schema"]

    def __init__(
        self,
        func: Callable,
        schema: Optional[vol.Schema],
        context: Optional[Context] = None,
    ) -> None:
        """Initialize a service."""
        self.job = HassJob(func)
        self.schema = schema


class ServiceCall:
    """Representation of a call to a service."""

    __slots__ = ["domain", "service", "data", "context"]

    def __init__(
        self,
        domain: str,
        service: str,
        data: Optional[Dict] = None,
        context: Optional[Context] = None,
    ) -> None:
        """Initialize a service call."""
        self.domain = domain.lower()
        self.service = service.lower()
        self.data = MappingProxyType(data or {})
        self.context = context or Context()

    def __repr__(self) -> str:
        """Return the representation of the service."""
        if self.data:
            return (
                f"<ServiceCall {self.domain}.{self.service} "
                f"(c:{self.context.id}): {util.repr_helper(self.data)}>"
            )

        return f"<ServiceCall {self.domain}.{self.service} (c:{self.context.id})>"


class ServiceRegistry:
    """Offer the services over the eventbus."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a service registry."""
        self._services: Dict[str, Dict[str, Service]] = {}
        self._hass = hass

    @property
    def services(self) -> Dict[str, Dict[str, Service]]:
        """Return dictionary with per domain a list of available services."""
        return run_callback_threadsafe(self._hass.loop, self.async_services).result()

    @callback
    def async_services(self) -> Dict[str, Dict[str, Service]]:
        """Return dictionary with per domain a list of available services.

        This method must be run in the event loop.
        """
        return {domain: self._services[domain].copy() for domain in self._services}

    def has_service(self, domain: str, service: str) -> bool:
        """Test if specified service exists.

        Async friendly.
        """
        return service.lower() in self._services.get(domain.lower(), [])

    def register(
        self,
        domain: str,
        service: str,
        service_func: Callable,
        schema: Optional[vol.Schema] = None,
    ) -> None:
        """
        Register a service.

        Schema is called to coerce and validate the service data.
        """
        run_callback_threadsafe(
            self._hass.loop, self.async_register, domain, service, service_func, schema
        ).result()

    @callback
    def async_register(
        self,
        domain: str,
        service: str,
        service_func: Callable,
        schema: Optional[vol.Schema] = None,
    ) -> None:
        """
        Register a service.

        Schema is called to coerce and validate the service data.

        This method must be run in the event loop.
        """
        domain = domain.lower()
        service = service.lower()
        service_obj = Service(service_func, schema)

        if domain in self._services:
            self._services[domain][service] = service_obj
        else:
            self._services[domain] = {service: service_obj}

        self._hass.bus.async_fire(
            EVENT_SERVICE_REGISTERED, {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler."""
        run_callback_threadsafe(
            self._hass.loop, self.async_remove, domain, service
        ).result()

    @callback
    def async_remove(self, domain: str, service: str) -> None:
        """Remove a registered service from service handler.

        This method must be run in the event loop.
        """
        domain = domain.lower()
        service = service.lower()

        if service not in self._services.get(domain, {}):
            _LOGGER.warning("Unable to remove unknown service %s/%s", domain, service)
            return

        self._services[domain].pop(service)

        if not self._services[domain]:
            self._services.pop(domain)

        self._hass.bus.async_fire(
            EVENT_SERVICE_REMOVED, {ATTR_DOMAIN: domain, ATTR_SERVICE: service}
        )

    def call(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict] = None,
        blocking: bool = False,
        context: Optional[Context] = None,
        limit: Optional[float] = SERVICE_CALL_LIMIT,
    ) -> Optional[bool]:
        """
        Call a service.

        See description of async_call for details.
        """
        return asyncio.run_coroutine_threadsafe(
            self.async_call(domain, service, service_data, blocking, context, limit),
            self._hass.loop,
        ).result()

    async def async_call(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict] = None,
        blocking: bool = False,
        context: Optional[Context] = None,
        limit: Optional[float] = SERVICE_CALL_LIMIT,
    ) -> Optional[bool]:
        """
        Call a service.

        Specify blocking=True to wait until service is executed.
        Waits a maximum of limit, which may be None for no timeout.

        If blocking = True, will return boolean if service executed
        successfully within limit.

        This method will fire an event to indicate the service has been called.

        Because the service is sent as an event you are not allowed to use
        the keys ATTR_DOMAIN and ATTR_SERVICE in your service_data.

        This method is a coroutine.
        """
        domain = domain.lower()
        service = service.lower()
        context = context or Context()
        service_data = service_data or {}

        try:
            handler = self._services[domain][service]
        except KeyError:
            raise ServiceNotFound(domain, service) from None

        if handler.schema:
            try:
                processed_data = handler.schema(service_data)
            except vol.Invalid:
                _LOGGER.debug(
                    "Invalid data for service call %s.%s: %s",
                    domain,
                    service,
                    service_data,
                )
                raise
        else:
            processed_data = service_data

        service_call = ServiceCall(domain, service, processed_data, context)

        self._hass.bus.async_fire(
            EVENT_CALL_SERVICE,
            {
                ATTR_DOMAIN: domain.lower(),
                ATTR_SERVICE: service.lower(),
                ATTR_SERVICE_DATA: service_data,
            },
            context=context,
        )

        coro = self._execute_service(handler, service_call)
        if not blocking:
            self._run_service_in_background(coro, service_call)
            return None

        task = self._hass.async_create_task(coro)
        try:
            await asyncio.wait({task}, timeout=limit)
        except asyncio.CancelledError:
            # Task calling us was cancelled, so cancel service call task, and wait for
            # it to be cancelled, within reason, before leaving.
            _LOGGER.debug("Service call was cancelled: %s", service_call)
            task.cancel()
            await asyncio.wait({task}, timeout=SERVICE_CALL_LIMIT)
            raise

        if task.cancelled():
            # Service call task was cancelled some other way, such as during shutdown.
            _LOGGER.debug("Service was cancelled: %s", service_call)
            raise asyncio.CancelledError
        if task.done():
            # Propagate any exceptions that might have happened during service call.
            task.result()
            # Service call completed successfully!
            return True
        # Service call task did not complete before timeout expired.
        # Let it keep running in background.
        self._run_service_in_background(task, service_call)
        _LOGGER.debug("Service did not complete before timeout: %s", service_call)
        return False

    def _run_service_in_background(
        self, coro_or_task: Union[Coroutine, asyncio.Task], service_call: ServiceCall
    ) -> None:
        """Run service call in background, catching and logging any exceptions."""

        async def catch_exceptions() -> None:
            try:
                await coro_or_task
            except Unauthorized:
                _LOGGER.warning(
                    "Unauthorized service called %s/%s",
                    service_call.domain,
                    service_call.service,
                )
            except asyncio.CancelledError:
                _LOGGER.debug("Service was cancelled: %s", service_call)
            except Exception:  
                _LOGGER.exception("Error executing service: %s", service_call)

        self._hass.async_create_task(catch_exceptions())

    async def _execute_service(
        self, handler: Service, service_call: ServiceCall
    ) -> None:
        """Execute a service."""
        if handler.job.job_type == HassJobType.Coroutinefunction:
            await handler.job.target(service_call)
        elif handler.job.job_type == HassJobType.Callback:
            handler.job.target(service_call)
        else:
            await self._hass.async_add_executor_job(handler.job.target, service_call)


class Config:
    """Configuration settings for Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new config object."""
        self.hass = hass

        self.latitude: float = 0
        self.longitude: float = 0
        self.elevation: int = 0
        self.location_name: str = "Home"
        self.time_zone: datetime.tzinfo = dt_util.UTC
        self.units: UnitSystem = METRIC_SYSTEM
        self.internal_url: Optional[str] = None
        self.external_url: Optional[str] = None

        self.config_source: str = "default"

        
        self.skip_pip: bool = False

        
        self.components: Set[str] = set()

     
        self.api: Optional[Any] = None

       
        self.config_dir: Optional[str] = None
        
        self.allowlist_external_dirs: Set[str] = set()

       
        self.allowlist_external_urls: Set[str] = set()

        
        self.media_dirs: Dict[str, str] = {}

        
        self.safe_mode: bool = False

        
        self.legacy_templates: bool = False

    def distance(self, lat: float, lon: float) -> Optional[float]:
        """Calculate distance from Home Assistant.

        Async friendly.
        """
        return self.units.length(
            location.distance(self.latitude, self.longitude, lat, lon), LENGTH_METERS
        )

    def path(self, *path: str) -> str:
        """Generate path to the file within the configuration directory.

        Async friendly.
        """
        if self.config_dir is None:
            raise HomeAssistantError("config_dir is not set")
        return os.path.join(self.config_dir, *path)

    def is_allowed_external_url(self, url: str) -> bool:
        """Check if an external URL is allowed."""
        parsed_url = f"{str(yarl.URL(url))}/"

        return any(
            allowed
            for allowed in self.allowlist_external_urls
            if parsed_url.startswith(allowed)
        )

    def is_allowed_path(self, path: str) -> bool:
        """Check if the path is valid for access from outside."""
        assert path is not None

        thepath = pathlib.Path(path)
        try:
           
            if thepath.exists():
                thepath = thepath.resolve()
            else:
                thepath = thepath.parent.resolve()
        except (FileNotFoundError, RuntimeError, PermissionError):
            return False

        for allowed_path in self.allowlist_external_dirs:
            try:
                thepath.relative_to(allowed_path)
                return True
            except ValueError:
                pass

        return False

    def as_dict(self) -> Dict:
        """Create a dictionary representation of the configuration.

        Async friendly.
        """
        time_zone = dt_util.UTC.zone
        if self.time_zone and getattr(self.time_zone, "zone"):
            time_zone = getattr(self.time_zone, "zone")

        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "unit_system": self.units.as_dict(),
            "location_name": self.location_name,
            "time_zone": time_zone,
            "components": self.components,
            "config_dir": self.config_dir,
            
            "whitelist_external_dirs": self.allowlist_external_dirs,
            "allowlist_external_dirs": self.allowlist_external_dirs,
            "allowlist_external_urls": self.allowlist_external_urls,
            "version": __version__,
            "config_source": self.config_source,
            "safe_mode": self.safe_mode,
            "state": self.hass.state.value,
            "external_url": self.external_url,
            "internal_url": self.internal_url,
        }

    def set_time_zone(self, time_zone_str: str) -> None:
        """Help to set the time zone."""
        time_zone = dt_util.get_time_zone(time_zone_str)

        if time_zone:
            self.time_zone = time_zone
            dt_util.set_default_time_zone(time_zone)
        else:
            raise ValueError(f"Received invalid time zone {time_zone_str}")

    @callback
    def _update(
        self,
        *,
        source: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        elevation: Optional[int] = None,
        unit_system: Optional[str] = None,
        location_name: Optional[str] = None,
        time_zone: Optional[str] = None,
        external_url: Optional[Union[str, dict]] = _UNDEF,
        internal_url: Optional[Union[str, dict]] = _UNDEF,
    ) -> None:
        """Update the configuration from a dictionary."""
        self.config_source = source
        if latitude is not None:
            self.latitude = latitude
        if longitude is not None:
            self.longitude = longitude
        if elevation is not None:
            self.elevation = elevation
        if unit_system is not None:
            if unit_system == CONF_UNIT_SYSTEM_IMPERIAL:
                self.units = IMPERIAL_SYSTEM
            else:
                self.units = METRIC_SYSTEM
        if location_name is not None:
            self.location_name = location_name
        if time_zone is not None:
            self.set_time_zone(time_zone)
        if external_url is not _UNDEF:
            self.external_url = cast(Optional[str], external_url)
        if internal_url is not _UNDEF:
            self.internal_url = cast(Optional[str], internal_url)

    async def async_update(self, **kwargs: Any) -> None:
        """Update the configuration from a dictionary."""
        self._update(source=SOURCE_STORAGE, **kwargs)
        await self.async_store()
        self.hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, kwargs)

    async def async_load(self) -> None:
        """Load [homeassistant] core config."""
        store = self.hass.helpers.storage.Store(
            CORE_STORAGE_VERSION, CORE_STORAGE_KEY, private=True
        )
        data = await store.async_load()

        async def migrate_base_url(_: Event) -> None:
            """Migrate base_url to internal_url/external_url."""
            if self.hass.config.api is None:
                return

            base_url = yarl.URL(self.hass.config.api.deprecated_base_url)

           
            if str(base_url.host).endswith(".local") or (
                network.is_ip_address(str(base_url.host))
                and network.is_private(ip_address(base_url.host))
            ):
                await self.async_update(
                    internal_url=network.normalize_url(str(base_url))
                )
                return

           
            if not (
                network.is_ip_address(str(base_url.host))
                and network.is_loopback(ip_address(base_url.host))
            ):
                await self.async_update(
                    external_url=network.normalize_url(str(base_url))
                )

        if data:
          
            if "external_url" not in data:
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_START, migrate_base_url
                )

            self._update(
                source=SOURCE_STORAGE,
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
                elevation=data.get("elevation"),
                unit_system=data.get("unit_system"),
                location_name=data.get("location_name"),
                time_zone=data.get("time_zone"),
                external_url=data.get("external_url", _UNDEF),
                internal_url=data.get("internal_url", _UNDEF),
            )

    async def async_store(self) -> None:
        """Store [homeassistant] core config."""
        time_zone = dt_util.UTC.zone
        if self.time_zone and getattr(self.time_zone, "zone"):
            time_zone = getattr(self.time_zone, "zone")

        data = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "unit_system": self.units.name,
            "location_name": self.location_name,
            "time_zone": time_zone,
            "external_url": self.external_url,
            "internal_url": self.internal_url,
        }

        store = self.hass.helpers.storage.Store(
            CORE_STORAGE_VERSION, CORE_STORAGE_KEY, private=True
        )
        await store.async_save(data)


def _async_create_timer(hass: HomeAssistant) -> None:
    """Create a timer that will start on HOMEASSISTANT_START."""
    handle = None
    timer_context = Context()

    def schedule_tick(now: datetime.datetime) -> None:
        """Schedule a timer tick when the next second rolls around."""
        nonlocal handle

        slp_seconds = 1 - (now.microsecond / 10 ** 6)
        target = monotonic() + slp_seconds
        handle = hass.loop.call_later(slp_seconds, fire_time_event, target)

    @callback
    def fire_time_event(target: float) -> None:
        """Fire next time event."""
        now = dt_util.utcnow()

        hass.bus.async_fire(
            EVENT_TIME_CHANGED, {ATTR_NOW: now}, time_fired=now, context=timer_context
        )

        late = monotonic() - target
        if late > 1:
            hass.bus.async_fire(
                EVENT_TIMER_OUT_OF_SYNC,
                {ATTR_SECONDS: late},
                time_fired=now,
                context=timer_context,
            )

        schedule_tick(now)

    @callback
    def stop_timer(_: Event) -> None:
        """Stop the timer."""
        if handle is not None:
            handle.cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_timer)

    _LOGGER.info("Timer:starting")
    schedule_tick(dt_util.utcnow())
