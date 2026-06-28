import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { FactorFilter, MarketFilter, SortBy, UiState } from '../types'

const initialState: UiState = {
  marketFilter: 'all',   // all | us | india | uk
  earlyOnly: false,
  whaleOnly: false,
  sectorFilter: null,
  sortBy: 'score',       // score | quality | factors | day | rvol
  search: '',
  selectedSymbol: null,  // drives DetailPanel
  factorSymbol: null,    // drives FactorModal (null = closed)
  factorFilter: 'all',   // all | pass | fail | risk
  toast: null,
}

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setMarketFilter: (s, a: PayloadAction<MarketFilter>) => { s.marketFilter = a.payload },
    toggleEarly: (s) => { s.earlyOnly = !s.earlyOnly },
    toggleWhale: (s) => { s.whaleOnly = !s.whaleOnly },
    setSectorFilter: (s, a: PayloadAction<string | null>) => { s.sectorFilter = a.payload },
    setSortBy: (s, a: PayloadAction<SortBy>) => { s.sortBy = a.payload },
    setSearch: (s, a: PayloadAction<string>) => { s.search = a.payload },
    selectSymbol: (s, a: PayloadAction<string | null>) => { s.selectedSymbol = a.payload },
    openFactors: (s, a: PayloadAction<string>) => { s.factorSymbol = a.payload; s.factorFilter = 'all' },
    closeFactors: (s) => { s.factorSymbol = null },
    setFactorFilter: (s, a: PayloadAction<FactorFilter>) => { s.factorFilter = a.payload },
    resetFilters: (s) => {
      s.marketFilter = 'all'; s.earlyOnly = false; s.whaleOnly = false
      s.sectorFilter = null; s.search = ''
    },
    toast: (s, a: PayloadAction<unknown>) => { s.toast = a.payload },
  },
})

export const {
  setMarketFilter, toggleEarly, toggleWhale, setSectorFilter, setSortBy,
  setSearch, selectSymbol, openFactors, closeFactors, setFactorFilter,
  resetFilters, toast,
} = uiSlice.actions
export default uiSlice.reducer
