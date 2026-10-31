export interface DisplayCapabilities {
  canRead: boolean; canSetPrimary: boolean; canPersist: boolean; recoveryAvailable: boolean;
  confirmationOwner: 'unavailable'; reason: string;
}
export interface LogicalMonitor {
  id: string; name: string; connectors: string[]; primary: boolean;
  x: number; y: number; scale: number; transform: number;
}
export interface PhysicalMonitor {
  connector: string; name: string; active: boolean; logicalId: string | null;
  width: number | null; height: number | null; refreshHz: number | null;
}
export interface DisplayState {
  revision: string; epoch: string; sequence: number;
  capabilities: DisplayCapabilities; logicalMonitors: LogicalMonitor[]; physicalMonitors: PhysicalMonitor[];
  transaction: null;
}
