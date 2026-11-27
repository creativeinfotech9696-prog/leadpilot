import axios from "axios";
import { createContext, useCallback, useContext } from "react";
import { useAuth } from "@clerk/react";
import { useQuery } from "@tanstack/react-query";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useApi() {
  const { getToken } = useAuth();
  return useCallback(async (method, path, data, config = {}) => {
    const token = await getToken();
    const res = await axios({ method, url: `${API}${path}`, data, ...config, headers: { Authorization: `Bearer ${token}`, ...(config.headers || {}) } });
    return res.data;
  }, [getToken]);
}

export const errMsg = (e) => e?.response?.data?.detail || e?.message || "Something went wrong";

export const WindowContext = createContext({ days: 14, setDays: () => {} });
export const useWindow = () => useContext(WindowContext);

export function useAnalysis() {
  const api = useApi();
  const { days } = useWindow();
  return useQuery({ queryKey: ["analysis", days], queryFn: () => api("get", `/analytics?days=${days}`) });
}

export function useRecs(status = "active") {
  const api = useApi();
  return useQuery({ queryKey: ["recs", status], queryFn: () => api("get", `/recommendations?status=${status}`) });
}
