import { configureStore } from '@reduxjs/toolkit';
// Import slice reducers here
import authReducer from './slices/authSlice';
import flowReducer from './slices/flowSlice';
// import chatReducer from './slices/chatSlice';
// import uiReducer from './slices/uiSlice';

export const store = configureStore({
  reducer: {
    // Add reducers here
    auth: authReducer,
    flow: flowReducer,
    // chat: chatReducer,
    // ui: uiReducer,
  },
  // Optional: Add middleware, e.g., for async actions or logging
  // middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(logger),
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch; 