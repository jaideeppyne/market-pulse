import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Watchlist', 'Portfolio', 'AlertRules', 'Journal'],
  endpoints: (b) => ({
    // ----- on-demand reads -----
    snapshot: b.query({ query: () => '/snapshot?light=true' }),
    analyze: b.query({ query: (sym) => `/analyze/${encodeURIComponent(sym)}` }),
    symbol: b.query({ query: (sym) => `/symbol/${encodeURIComponent(sym)}` }),
    sectors: b.query({ query: () => '/sectors' }),
    news: b.query({ query: () => '/news' }),
    earnings: b.query({ query: () => '/earnings' }),
    edge: b.query({ query: () => '/edge' }),
    regime: b.query({ query: () => '/regime' }),
    discover: b.query({ query: () => '/discover' }),
    factorsCatalog: b.query({ query: () => '/factors' }),
    lastFullScan: b.query({ query: () => '/last_full_scan' }),
    jobStatus: b.query({ query: (id) => `/job_status/${id}` }),
    jobResult: b.query({ query: (id) => `/job_result/${id}` }),
    recentAlerts: b.query({ query: () => '/alerts/recent?limit=50' }),

    // ----- watchlist -----
    watchlist: b.query({ query: () => '/watchlist', providesTags: ['Watchlist'] }),
    addWatch: b.mutation({
      query: (body) => ({ url: '/watchlist', method: 'POST', body }),
      invalidatesTags: ['Watchlist'],
    }),
    removeWatch: b.mutation({
      query: (sym) => ({ url: `/watchlist/${encodeURIComponent(sym)}`, method: 'DELETE' }),
      invalidatesTags: ['Watchlist'],
    }),

    // ----- alert rules -----
    alertRules: b.query({ query: () => '/alert_rules', providesTags: ['AlertRules'] }),
    addAlertRule: b.mutation({
      query: (body) => ({ url: '/alert_rules', method: 'POST', body }),
      invalidatesTags: ['AlertRules'],
    }),
    deleteAlertRule: b.mutation({
      query: (id) => ({ url: `/alert_rules/${id}`, method: 'DELETE' }),
      invalidatesTags: ['AlertRules'],
    }),

    // ----- portfolio / journal -----
    portfolio: b.query({ query: () => '/portfolio', providesTags: ['Portfolio'] }),
    journal: b.query({ query: () => '/journal', providesTags: ['Journal'] }),
    addPosition: b.mutation({
      query: (body) => ({ url: '/portfolio', method: 'POST', body }),
      invalidatesTags: ['Portfolio', 'Journal'],
    }),
    updatePosition: b.mutation({
      query: ({ symbol, ...body }) => ({ url: `/position/${encodeURIComponent(symbol)}/update`, method: 'POST', body }),
      invalidatesTags: ['Portfolio'],
    }),
    closePosition: b.mutation({
      query: ({ symbol, ...body }) => ({ url: `/position/${encodeURIComponent(symbol)}/close`, method: 'POST', body }),
      invalidatesTags: ['Portfolio', 'Journal'],
    }),
    startFullScan: b.mutation({
      query: () => ({ url: '/full_exhaustive_scan', method: 'POST', body: {} }),
    }),
  }),
})

export const {
  useSnapshotQuery, useAnalyzeQuery, useLazyAnalyzeQuery, useSectorsQuery,
  useNewsQuery, useEarningsQuery, useEdgeQuery, useLazyEdgeQuery, useRegimeQuery, useDiscoverQuery,
  useLazyDiscoverQuery, useFactorsCatalogQuery, useLastFullScanQuery,
  useLazyJobStatusQuery, useLazyJobResultQuery, useRecentAlertsQuery,
  useWatchlistQuery, useAddWatchMutation, useRemoveWatchMutation,
  useAlertRulesQuery, useAddAlertRuleMutation, useDeleteAlertRuleMutation,
  usePortfolioQuery, useJournalQuery, useAddPositionMutation,
  useUpdatePositionMutation, useClosePositionMutation, useStartFullScanMutation,
} = api
