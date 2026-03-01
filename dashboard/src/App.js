import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import Recommendations from './pages/Recommendations';
import Navbar from './components/Navbar';
import './styles/App.css';

function App() {
  const [user, setUser] = useState(null);

  // On mount, check localStorage for saved username
  useEffect(() => {
    const savedUsername = localStorage.getItem('adhdlockin_username');
    if (savedUsername) {
      setUser({ username: savedUsername, userId: savedUsername });
    }
  }, []);

  const handleLogin = (userData) => {
    setUser(userData);
    localStorage.setItem('adhdlockin_username', userData.username);
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('adhdlockin_username');
  };

  return (
    <Router>
      <div className="app">
        {user && <Navbar user={user} onLogout={handleLogout} />}
        <Routes>
          <Route
            path="/"
            element={
              user ? <Dashboard user={user} /> : <Auth onLogin={handleLogin} />
            }
          />
          <Route
            path="/recommendations"
            element={
              user ? <Recommendations user={user} /> : <Navigate to="/" />
            }
          />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
