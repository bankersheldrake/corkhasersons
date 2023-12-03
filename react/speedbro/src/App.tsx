// App.tsx
import React from 'react';
import SpeedTest from './SpeedTest';

const App: React.FC = () => {
  return (
    <div className="App">
      <header className="App-header">
        <h1>SpeedBro Internet Speed Test</h1>
        <SpeedTest />
      </header>
    </div>
  );
}

export default App;
