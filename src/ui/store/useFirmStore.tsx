import { create } from 'zustand';

interface FirmState {
  userId: string | null;
  firmId: string | null;
  isLoading: boolean;
  setAuth: (userId: string | null, firmId: string | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useFirmStore = create<FirmState>((set) => ({
  userId: null,
  firmId: null,
  isLoading: true, // Starts true while we check Supabase on load
  setAuth: (userId, firmId) => set({ userId, firmId, isLoading: false }),
  setLoading: (loading) => set({ isLoading: loading }),
}));