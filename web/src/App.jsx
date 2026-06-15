import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import FactorModal from './components/FactorModal'

const CommandCenter = lazy(() => import('./pages/CommandCenter'))
const Watchlist = lazy(() => import('./pages/Watchlist'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Radar = lazy(() => import('./pages/Radar'))
const Sectors = lazy(() => import('./pages/Sectors'))
const Earnings = lazy(() => import('./pages/Earnings'))
const News = lazy(() => import('./pages/News'))
const Edge = lazy(() => import('./pages/Edge'))

function Loading() {
  return <div className="route-loading"><span className="panel__pulse" /> Loading…</div>
}

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/radar" element={<Radar />} />
          <Route path="/sectors" element={<Sectors />} />
          <Route path="/earnings" element={<Earnings />} />
          <Route path="/news" element={<News />} />
          <Route path="/edge" element={<Edge />} />
          <Route path="*" element={<CommandCenter />} />
        </Routes>
      </Suspense>
      <FactorModal />
    </Layout>
  )
}
