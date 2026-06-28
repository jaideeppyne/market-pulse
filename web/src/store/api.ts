import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type {
  AddPositionBody,
  AlertRuleBody,
  AlertRulesResponse,
  ClosePositionBody,
  EdgeResponse,
  JournalResponse,
  NewsItem,
  PortfolioResponse,
  Row,
  Snapshot,
  StartFullScanResponse,
  UpdatePositionBody,
  WatchBody,
  WatchlistResponse,
} from '../types'

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Watchlist', 'Portfolio', 'AlertRules', 'Journal'],
  endpoints: (b) => ({
    // ----- on-demand reads -----
    snapshot: b.query<Snapshot, void>({ query: () => '/snapshot?light=true' }),
    analyze: b.query<Row, string>({ query: (sym) => `/analyze/${encodeURIComponent(sym)}` }),
    symbol: b.query<Row, string>({ query: (sym) => `/symbol/${encodeURIComponent(sym)}` }),
    sectors: b.query<Snapshot['sectors'], void>({ query: () => '/sectors' }),
    news: b.query<{ live?: NewsItem[]; stored?: NewsItem[] }, void>({ query: () => '/news' }),
    earnings: b.query<Snapshot['earnings'], void>({ query: () => '/earnings' }),
    edge: b.query<EdgeResponse, void>({ query: () => '/edge' }),
    regime: b.query<Record<string, unknown>, void>({ query: () => '/regime' }),
    discover: b.query<Snapshot, void>({ query: () => '/discover' }),
    factorsCatalog: b.query<Record<string, unknown>, void>({ query: () => '/factors' }),
    lastFullScan: b.query<Record<string, unknown>, void>({ query: () => '/last_full_scan' }),
    jobStatus: b.query<Record<string, unknown>, string | number>({ query: (id) => `/job_status/${id}` }),
    jobResult: b.query<Record<string, unknown>, string | number>({ query: (id) => `/job_result/${id}` }),
    recentAlerts: b.query<Record<string, unknown>[], void>({ query: () => '/alerts/recent?limit=50' }),

    // ----- watchlist -----
    watchlist: b.query<WatchlistResponse, void>({ query: () => '/watchlist', providesTags: ['Watchlist'] }),
    addWatch: b.mutation<WatchlistResponse, WatchBody>({
      query: (body) => ({ url: '/watchlist', method: 'POST', body }),
      invalidatesTags: ['Watchlist'],
    }),
    removeWatch: b.mutation<{ ok?: boolean }, string>({
      query: (sym) => ({ url: `/watchlist/${encodeURIComponent(sym)}`, method: 'DELETE' }),
      invalidatesTags: ['Watchlist'],
    }),

    // ----- alert rules -----
    alertRules: b.query<AlertRulesResponse, void>({ query: () => '/alert_rules', providesTags: ['AlertRules'] }),
    addAlertRule: b.mutation<AlertRulesResponse, AlertRuleBody>({
      query: (body) => ({ url: '/alert_rules', method: 'POST', body }),
      invalidatesTags: ['AlertRules'],
    }),
    deleteAlertRule: b.mutation<{ ok?: boolean }, string | number>({
      query: (id) => ({ url: `/alert_rules/${id}`, method: 'DELETE' }),
      invalidatesTags: ['AlertRules'],
    }),

    // ----- portfolio / journal -----
    portfolio: b.query<PortfolioResponse, void>({ query: () => '/portfolio', providesTags: ['Portfolio'] }),
    journal: b.query<JournalResponse, void>({ query: () => '/journal', providesTags: ['Journal'] }),
    addPosition: b.mutation<PortfolioResponse, AddPositionBody>({
      query: (body) => ({ url: '/portfolio', method: 'POST', body }),
      invalidatesTags: ['Portfolio', 'Journal'],
    }),
    updatePosition: b.mutation<PortfolioResponse, UpdatePositionBody>({
      query: ({ symbol, ...body }) => ({ url: `/position/${encodeURIComponent(symbol)}/update`, method: 'POST', body }),
      invalidatesTags: ['Portfolio'],
    }),
    closePosition: b.mutation<PortfolioResponse, ClosePositionBody>({
      query: ({ symbol, ...body }) => ({ url: `/position/${encodeURIComponent(symbol)}/close`, method: 'POST', body }),
      invalidatesTags: ['Portfolio', 'Journal'],
    }),
    startFullScan: b.mutation<StartFullScanResponse, void>({
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
