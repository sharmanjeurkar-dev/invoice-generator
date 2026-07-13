import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  userId: string | null;
  firmId: string | null;
  isLoading: boolean; // 👈 1. Add isLoading
  
  setAuth: (userId: string | null, firmId: string | null) => void;
  setFirmId: (id: string | null) => void;
  setLoading: (loading: boolean) => void; // 👈 2. Add setLoading
}

export const useFirmStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: null,
      firmId: null,
      isLoading: true, // 👈 3. Start as true so the UI can show a spinner initially
      
      // 4. Update setAuth to also turn off the loading state
      setAuth: (userId, firmId) => set({ userId, firmId, isLoading: false }),
      
      setFirmId: (id) => set({ firmId: id }),
      
      // 5. Implement setLoading
      setLoading: (loading) => set({ isLoading: loading }),
    }),
    {
      name: 'ledger-auth-storage', 
      // 6. 🛡️ CRITICAL: Tell Zustand NOT to save 'isLoading' to local storage
      partialize: (state) => ({ 
        userId: state.userId, 
        firmId: state.firmId 
      }),
    }
  )
)