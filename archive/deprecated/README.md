# Deprecated Code Archive

## DO NOT USE FILES IN THIS DIRECTORY

### supervisor_v2_DEPRECATED.py
- **Deprecated**: 2025-09-01
- **Reason**: Critical performance regression (200ms failover vs <10ms target)
- **Issues**:
  - Missing sentinel-based detection
  - No standby respawn after failover  
  - Broken shutdown command handling
- **Replacement**: Use `supervisor_v2_fixed.py` (now main AudioSupervisor)
- **Status**: Archived for historical reference only