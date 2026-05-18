function Hero() {
  return (
    <div style={{
      backgroundColor: '#eaf0fb',
      color: '#1a1a2e',
      padding: '5rem 2rem',
      textAlign: 'center',
    }}>

      <h1 style={{ fontSize: '2.2rem', marginBottom: '1rem' }}>
        Welcome to the Institute HPC Resource Portal
      </h1>

      <p style={{ 
        fontSize: '1.1rem', 
        color: '#4a5568', 
        marginBottom: '2rem',
        maxWidth: '600px',
        margin: '0 auto 2rem auto'
      }}>
        Submit jobs, monitor cluster health, and manage your compute 
        allocations — all in one place.
      </p>

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
        <button style={{
          backgroundColor: '#4f8ef7',
          color: '#fff',
          border: 'none',
          padding: '12px 28px',
          borderRadius: '6px',
          fontSize: '1rem',
          cursor: 'pointer'
        }}>
          Request Access
        </button>

        <button style={{
          backgroundColor: 'transparent',
          color: '#1a1a2e',
          border: '1px solid #1a1a2e',
          padding: '12px 28px',
          borderRadius: '6px',
          fontSize: '1rem',
          cursor: 'pointer'
        }}>
          View Documentation
        </button>
      </div>

    </div>
  )
}

export default Hero