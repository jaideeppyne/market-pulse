import { configureStore } from '@reduxjs/toolkit'
import { api } from './api'
import live from './liveSlice'
import ui from './uiSlice'
import { createWsMiddleware } from './wsMiddleware'

export const store = configureStore({
  reducer: {
    [api.reducerPath]: api.reducer,
    live,
    ui,
  },
  middleware: (getDefault) =>
    getDefault({ serializableCheck: false }).concat(api.middleware, createWsMiddleware()),
})

// open the live websocket
store.dispatch({ type: 'ws/connect' })

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
