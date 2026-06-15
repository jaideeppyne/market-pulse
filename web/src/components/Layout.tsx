import Rail from './Rail'
import Topbar from './Topbar'

export default function Layout({ children }) {
  return (
    <>
      <div className="bg-glow-cyan" />
      <div className="bg-glow-violet" />
      <div className="app">
        <Rail />
        <div className="center">
          <Topbar />
          <div className="center__main">{children}</div>
        </div>
      </div>
      <footer className="footer">Pulse Terminal · Market Pulse engine · US + India + UK scanner · Yahoo + RSS</footer>
    </>
  )
}
