from abc import ABC, abstractmethod
from typing import Any, Optional

class StateBackend(ABC):
    """Terraform state backend abstract base class"""
    
    @abstractmethod
    def list_states(self, prefix: str = "") -> list[str]:
        """
        List all state files in the backend
        
        Args:
            prefix: Filter prefix
            
        Returns:
            List of state file paths
        """
        pass

    @abstractmethod
    def get_state(self, path: str) -> dict[str, Any]:
        """
        Get state content
        
        Args:
            path: State file path
            
        Returns:
            Parsed state dictionary
        """
        pass
