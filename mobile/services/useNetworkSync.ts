import { useEffect, useState } from "react";
import NetInfo from "@react-native-community/netinfo";
import { syncPendingReports } from "./sync";
import { countPendingReports } from "../database/db";

export function useNetworkSync() {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  const [pendingCount, setPendingCount] = useState(0);

  async function refreshPendingCount() {
    setPendingCount(await countPendingReports());
  }

  async function runSync() {
    const result = await syncPendingReports();
    await refreshPendingCount();
    return result;
  }

  useEffect(() => {
    refreshPendingCount();
    const unsubscribe = NetInfo.addEventListener((state) => {
      const online = Boolean(state.isConnected && state.isInternetReachable !== false);
      setIsOnline(online);
      // Sync whenever we are (or become) online -- including at app start with leftovers in the queue.
      if (online) runSync().catch(() => {});
    });
    return unsubscribe;
  }, []);

  return { isOnline, pendingCount, runSync, refreshPendingCount };
}
