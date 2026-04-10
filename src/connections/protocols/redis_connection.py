"""Redis connection for SONiC database access."""

import redis
from typing import Optional, Dict, Any, List, Union
from connections.base_connection import BaseConnection
from core.exceptions import ConnectionError, TimeoutError
from core.logger import get_logger

logger = get_logger(__name__)


class RedisConnection(BaseConnection):
    """Redis connection for SONiC database operations."""
    
    # SONiC database IDs
    APPL_DB = 0
    ASIC_DB = 1
    COUNTERS_DB = 2
    LOGLEVEL_DB = 3
    CONFIG_DB = 4
    FLEX_COUNTER_DB = 5
    STATE_DB = 6
    SNMP_OVERLAY_DB = 7
    
    def __init__(
        self,
        host: str,
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        username: Optional[str] = None,
        socket_timeout: int = 30,
        socket_connect_timeout: int = 30,
        socket_keepalive: bool = True,
        socket_keepalive_options: Optional[Dict] = None,
        decode_responses: bool = True,
        **kwargs
    ):
        """
        Initialize Redis connection.
        
        Args:
            host: Redis server hostname/IP
            port: Redis server port
            db: Database number
            password: Redis password
            username: Redis username (Redis 6+)
            socket_timeout: Socket timeout
            socket_connect_timeout: Connection timeout
            socket_keepalive: Enable keepalive
            socket_keepalive_options: Keepalive options
            decode_responses: Decode responses to strings
        """
        super().__init__(host, username or "", password or "", port, socket_timeout)
        
        self.db = db
        self.decode_responses = decode_responses
        self.socket_connect_timeout = socket_connect_timeout
        self.socket_keepalive = socket_keepalive
        self.socket_keepalive_options = socket_keepalive_options or {}
        self._connection_params = kwargs
        
        logger.info(f"Initialized Redis connection to {host}:{port} DB:{db}")
    
    def connect(self) -> bool:
        """
        Establish Redis connection.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            ConnectionError: If connection fails
            TimeoutError: If connection times out
        """
        try:
            logger.info(f"Connecting to Redis {self.host}:{self.port} DB:{self.db}")
            
            connection_params = {
                'host': self.host,
                'port': self.port,
                'db': self.db,
                'socket_timeout': self.timeout,
                'socket_connect_timeout': self.socket_connect_timeout,
                'socket_keepalive': self.socket_keepalive,
                'socket_keepalive_options': self.socket_keepalive_options,
                'decode_responses': self.decode_responses,
            }
            
            if self.password:
                connection_params['password'] = self.password
            
            if self.username:
                connection_params['username'] = self.username
            
            connection_params.update(self._connection_params)
            
            self.session = redis.Redis(**connection_params)
            
            # Test connection
            self.session.ping()
            
            logger.info(f"Successfully connected to Redis {self.host}")
            return True
            
        except redis.AuthenticationError as e:
            logger.error(f"Redis authentication failed for {self.host}: {e}")
            raise ConnectionError(f"Authentication failed: {e}")
            
        except redis.TimeoutError as e:
            logger.error(f"Redis connection timeout for {self.host}: {e}")
            raise TimeoutError(f"Connection timeout: {e}")
            
        except Exception as e:
            logger.error(f"Error connecting to Redis {self.host}: {e}")
            raise ConnectionError(f"Redis connection failed: {e}")
    
    def disconnect(self) -> bool:
        """
        Close Redis connection.
        
        Returns:
            bool: True if disconnection successful
        """
        try:
            if self.session:
                logger.info(f"Disconnecting from Redis {self.host}")
                self.session.close()
                self.session = None
                logger.info(f"Disconnected from Redis {self.host}")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from Redis {self.host}: {e}")
            return False
    
    def is_alive(self) -> bool:
        """
        Check if Redis connection is alive.
        
        Returns:
            bool: True if connection is alive
        """
        try:
            if self.session:
                return self.session.ping()
            return False
        except Exception:
            return False
    
    def send_command(self, command: str, **kwargs) -> Any:
        """
        Execute Redis command (not typically used, use specific methods).
        
        Args:
            command: Redis command
            
        Returns:
            Command result
        """
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        
        try:
            return self.session.execute_command(command)
        except Exception as e:
            logger.error(f"Error executing Redis command: {e}")
            raise ConnectionError(f"Command execution failed: {e}")
    
    def send_config(self, config: str, **kwargs) -> str:
        """Not applicable for Redis."""
        raise NotImplementedError("Config commands not applicable for Redis")
    
    # Redis-specific methods
    
    def get(self, key: str) -> Optional[str]:
        """Get value for key."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.get(key)
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set key-value pair."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.set(key, value, ex=ex)
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.hget(name, key)
    
    def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields and values."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.hgetall(name)
    
    def hset(self, name: str, key: str, value: str) -> int:
        """Set hash field value."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.hset(name, key, value)
    
    def hmset(self, name: str, mapping: Dict[str, str]) -> bool:
        """Set multiple hash fields."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.hmset(name, mapping)
    
    def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.keys(pattern)
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.delete(*keys)
    
    def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.exists(*keys)
    
    def scan_iter(self, match: Optional[str] = None, count: int = 100):
        """Iterate over keys matching pattern."""
        if not self.is_alive():
            raise ConnectionError(f"Not connected to Redis {self.host}")
        return self.session.scan_iter(match=match, count=count)
    
    def __repr__(self) -> str:
        """String representation of connection."""
        return f"RedisConnection(host={self.host}, port={self.port}, db={self.db})"