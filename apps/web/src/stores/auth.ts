import { create } from 'zustand'
import type { User } from '../types'

interface AuthState {
  user: User | null
  setSession: (token: string, user: User) => void
  logout: () => void
}

const storedUser = localStorage.getItem('carerelay-user')

export const useAuth = create<AuthState>((set) => ({
  user: storedUser ? JSON.parse(storedUser) as User : null,
  setSession: (token, user) => {
    localStorage.setItem('carerelay-token', token)
    localStorage.setItem('carerelay-user', JSON.stringify(user))
    set({ user })
  },
  logout: () => {
    localStorage.removeItem('carerelay-token')
    localStorage.removeItem('carerelay-user')
    set({ user: null })
  },
}))

