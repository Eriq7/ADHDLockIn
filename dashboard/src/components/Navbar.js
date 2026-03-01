import React from 'react';
import { Link, useLocation } from 'react-router-dom';

function Navbar({ user, onLogout }) {
  const location = useLocation();

  return (
    <nav className="navbar">
      <div className="navbar-brand">ADHDLockIn</div>
      <div className="navbar-links">
        <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
          Dashboard
        </Link>
        <Link to="/recommendations" className={`nav-link ${location.pathname === '/recommendations' ? 'active' : ''}`}>
          Recommendations
        </Link>
      </div>
      <div className="navbar-user">
        <span className="navbar-username">{user.username}</span>
        <button className="btn btn-logout" onClick={onLogout}>Logout</button>
      </div>
    </nav>
  );
}

export default Navbar;
