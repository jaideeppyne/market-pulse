import Rail from './Rail'
import Topbar from './Topbar'

export default function Layout({ children }) {
  return (
    <>
      <div className="app">
        <Rail />
        <div className="center">
          <Topbar />
          <div className="center__main">{children}</div>
        </div>
      </div>
      <footer className="footer">Market Pulse · AI-style signal workspace · US + India scanner</footer>
    </>
  )
}
