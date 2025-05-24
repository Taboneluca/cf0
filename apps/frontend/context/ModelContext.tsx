"use client"

import { createContext, useState, useContext, useEffect, ReactNode } from 'react'
import { useLocalStorage } from '@/hooks/useLocalStorage'

interface ModelContextType {
  model: string
  setModel: (model: string) => void
  isLoading: boolean
}

const DEFAULT_MODEL = "openai:gpt-4o" // Fallback default

const ModelContext = createContext<ModelContextType>({
  model: DEFAULT_MODEL,
  setModel: () => {},
  isLoading: true
})

export function ModelProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true)
  const [model, setModelState] = useLocalStorage('cf0-model', DEFAULT_MODEL)
  
  // Function to set model and also persist to Supabase if possible
  const setModel = async (newModel: string) => {
    console.log('ModelContext: Setting model to', newModel);
    setModelState(newModel)
    
    // Optional: save to user's profile in Supabase
    try {
      // This would be the place to save the user preference to a backend
      // const { data, error } = await supabase.from('profiles').update({ default_model: newModel })
    } catch (error) {
      console.error('Error saving model preference:', error)
    }
  }
  
  // Initialize model 
  useEffect(() => {
    const init = async () => {
      console.log('ModelContext: Initialized with model', model);
      setIsLoading(false)
    }
    
    init()
  }, [model])
  
  return (
    <ModelContext.Provider value={{ model, setModel, isLoading }}>
      {children}
    </ModelContext.Provider>
  )
}

export const useModel = () => {
  const context = useContext(ModelContext);
  if (!context) {
    throw new Error('useModel must be used within a ModelProvider');
  }
  return context;
} 