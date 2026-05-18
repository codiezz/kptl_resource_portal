function Navbar() {
  return (
    <nav style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '0 2rem',
      height: '60px',
      backgroundColor: '#1a1a2e',
      color: '#fff',
    }}>

      <div style={{ fontWeight: 'bold', fontSize: '1.2rem' }}>
        Institute HPC Portal
      </div>

      <div style={{ display: 'flex', gap: '2rem' }}>
        <a href="#" style={{ color: '#fff', textDecoration: 'none' }}>Home</a>
        <a href="#" style={{ color: '#fff', textDecoration: 'none' }}>Jobs</a>
        <a href="#" style={{ color: '#fff', textDecoration: 'none' }}>Docs</a>
        <a href="#" style={{ color: '#fff', textDecoration: 'none' }}>Support</a>
      </div>

      <div style={{
        backgroundColor: '#4f8ef7',
        padding: '8px 18px',
        borderRadius: '6px',
        cursor: 'pointer',
        fontSize: '0.9rem'
      }}>
        Login
      </div>

    </nav>
  )
}

export default Navbar