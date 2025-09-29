import React, { createContext, useContext, useReducer, useEffect } from 'react';

// Initial state
const initialState = {
  currentCase: null,
  chatMessages: {},
  ongoingQueries: {},
  sidebarOpen: true,
  globalLoading: false
};

// Action types
const ActionTypes = {
  SET_CURRENT_CASE: 'SET_CURRENT_CASE',
  SET_SIDEBAR_OPEN: 'SET_SIDEBAR_OPEN',
  SET_GLOBAL_LOADING: 'SET_GLOBAL_LOADING',
  SET_CHAT_MESSAGES: 'SET_CHAT_MESSAGES',
  ADD_CHAT_MESSAGE: 'ADD_CHAT_MESSAGE',
  SET_ONGOING_QUERY: 'SET_ONGOING_QUERY',
  CLEAR_ONGOING_QUERY: 'CLEAR_ONGOING_QUERY',
  CLEAR_CASE_DATA: 'CLEAR_CASE_DATA'
};

// Reducer
const appReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_CURRENT_CASE:
      return {
        ...state,
        currentCase: action.payload
      };
    
    case ActionTypes.SET_SIDEBAR_OPEN:
      return {
        ...state,
        sidebarOpen: action.payload
      };
    
    case ActionTypes.SET_GLOBAL_LOADING:
      return {
        ...state,
        globalLoading: action.payload
      };
    
    case ActionTypes.SET_CHAT_MESSAGES:
      return {
        ...state,
        chatMessages: {
          ...state.chatMessages,
          [action.payload.caseNumber]: action.payload.messages
        }
      };
    
    case ActionTypes.ADD_CHAT_MESSAGE:
      const caseNumber = action.payload.caseNumber;
      const existingMessages = state.chatMessages[caseNumber] || [];
      return {
        ...state,
        chatMessages: {
          ...state.chatMessages,
          [caseNumber]: [...existingMessages, action.payload.message]
        }
      };
    
    case ActionTypes.SET_ONGOING_QUERY:
      return {
        ...state,
        ongoingQueries: {
          ...state.ongoingQueries,
          [action.payload.caseNumber]: action.payload.query
        }
      };
    
    case ActionTypes.CLEAR_ONGOING_QUERY:
      const { [action.payload.caseNumber]: removed, ...remainingQueries } = state.ongoingQueries;
      return {
        ...state,
        ongoingQueries: remainingQueries
      };
    
    case ActionTypes.CLEAR_CASE_DATA:
      const { [action.payload.caseNumber]: removedMessages, ...remainingMessages } = state.chatMessages;
      const { [action.payload.caseNumber]: removedQuery, ...remainingOngoingQueries } = state.ongoingQueries;
      return {
        ...state,
        chatMessages: remainingMessages,
        ongoingQueries: remainingOngoingQueries
      };
    
    default:
      return state;
  }
};

// Context
const AppContext = createContext();

// Provider component
export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // Load state from localStorage on mount
  useEffect(() => {
    const savedState = localStorage.getItem('ufdr-app-state');
    if (savedState) {
      try {
        const parsedState = JSON.parse(savedState);
        if (parsedState.currentCase) {
          dispatch({ type: ActionTypes.SET_CURRENT_CASE, payload: parsedState.currentCase });
        }
        if (parsedState.chatMessages) {
          // Restore chat messages for all cases and convert timestamps back to Date objects
          Object.entries(parsedState.chatMessages).forEach(([caseNumber, messages]) => {
            const processedMessages = messages.map(message => ({
              ...message,
              timestamp: message.timestamp ? new Date(message.timestamp) : new Date()
            }));
            dispatch({ 
              type: ActionTypes.SET_CHAT_MESSAGES, 
              payload: { caseNumber, messages: processedMessages } 
            });
          });
        }
      } catch (error) {
        console.error('Error loading saved state:', error);
      }
    }
  }, []);

  // Save state to localStorage whenever it changes
  useEffect(() => {
    const stateToSave = {
      currentCase: state.currentCase,
      chatMessages: state.chatMessages
    };
    localStorage.setItem('ufdr-app-state', JSON.stringify(stateToSave));
  }, [state.currentCase, state.chatMessages]);

  // Actions
  const actions = {
    setCurrentCase: (caseData) => {
      // Clear chat messages for the new case to start fresh
      if (caseData && caseData.case_number) {
        dispatch({ 
          type: ActionTypes.SET_CHAT_MESSAGES, 
          payload: { caseNumber: caseData.case_number, messages: [] } 
        });
        // Also clear any ongoing queries for the new case
        dispatch({ 
          type: ActionTypes.CLEAR_ONGOING_QUERY, 
          payload: { caseNumber: caseData.case_number } 
        });
      }
      dispatch({ type: ActionTypes.SET_CURRENT_CASE, payload: caseData });
    },
    
    setSidebarOpen: (isOpen) => {
      dispatch({ type: ActionTypes.SET_SIDEBAR_OPEN, payload: isOpen });
    },
    
    setGlobalLoading: (isLoading) => {
      dispatch({ type: ActionTypes.SET_GLOBAL_LOADING, payload: isLoading });
    },
    
    setChatMessages: (caseNumber, messages) => {
      dispatch({ 
        type: ActionTypes.SET_CHAT_MESSAGES, 
        payload: { caseNumber, messages } 
      });
    },
    
    addChatMessage: (caseNumber, message) => {
      dispatch({ 
        type: ActionTypes.ADD_CHAT_MESSAGE, 
        payload: { caseNumber, message } 
      });
    },
    
    setOngoingQuery: (caseNumber, query) => {
      dispatch({ 
        type: ActionTypes.SET_ONGOING_QUERY, 
        payload: { caseNumber, query } 
      });
    },
    
    clearOngoingQuery: (caseNumber) => {
      dispatch({ 
        type: ActionTypes.CLEAR_ONGOING_QUERY, 
        payload: { caseNumber } 
      });
    },
    
    clearCaseData: (caseNumber) => {
      dispatch({ 
        type: ActionTypes.CLEAR_CASE_DATA, 
        payload: { caseNumber } 
      });
    }
  };

  return (
    <AppContext.Provider value={{ state, actions }}>
      {children}
    </AppContext.Provider>
  );
};

// Custom hook to use the context
export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

export default AppContext;
