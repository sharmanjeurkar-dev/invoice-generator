import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  userId: string | null;
  firmId: string | null;
  
  // 1. Define the function signature in the interface
  setAuth: (userId: string | null, firmId: string | null) => void;
  setFirmId: (id: string | null) => void;
}

export const useFirmStore = create<AuthState>()(
  persist(
    (set) => ({
      userId: null,
      firmId: null,
      
      // 2. Implement the function so AuthProvider can actually call it
      setAuth: (userId, firmId) => set({ userId, firmId }),
      
      setFirmId: (id) => set({ firmId: id }),
    }),
    {
      name: 'ledger-auth-storage', 
    }
  )
)