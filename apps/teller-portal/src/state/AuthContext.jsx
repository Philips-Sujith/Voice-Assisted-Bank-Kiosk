import React, { createContext, useContext, useState } from 'react';

const AuthContext = createContext({
  user: null,
  login: () => {},
  logout: () => {},
  isAuthenticated: false
});

export const PRESET_ACCOUNTS = [
  {
    staff_id: 'teller',
    name: 'Arun Kumar',
    role: 'Teller / Branch Staff',
    portal: 'teller',
    terminal_id: 'ST-042',
    branch_id: '014',
    avatar: 'AK',
    password: 'Password@123'
  },
  {
    staff_id: 'manager',
    name: 'Rajesh Sharma',
    role: 'Branch Manager',
    portal: 'manager',
    terminal_id: 'BM-001',
    branch_id: '014',
    avatar: 'RS',
    password: 'Password@123'
  }
];

export const AuthProvider = ({ children }) => {
  // Default logged in as teller for instant dev access or set to null
  const [user, setUser] = useState(PRESET_ACCOUNTS[0]);

  const login = (username, password) => {
    const found = PRESET_ACCOUNTS.find(
      (acc) => (acc.staff_id === username || acc.portal === username) && acc.password === password
    );

    if (found) {
      setUser(found);
      return { success: true, user: found };
    }

    return { success: false, message: 'Invalid Staff ID or Password. Check preset credentials below.' };
  };

  const logout = () => {
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        isAuthenticated: Boolean(user)
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
