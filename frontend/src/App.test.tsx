import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import i18n from './i18n'

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  )
}

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18n.changeLanguage('en')
})

test('the placeholder page shows the title and the clinical notice', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('The service is not running.')))
  renderApp()
  expect(screen.getByRole('heading', { level: 1, name: 'Rozmarra' })).toBeInTheDocument()
  expect(
    screen.getByText(
      'Rozmarra supports clinical decisions. It does not replace the judgement of a doctor.',
    ),
  ).toBeInTheDocument()
  expect(screen.getByText('Synthetic data')).toBeInTheDocument()
  expect(await screen.findByText('Not connected')).toBeInTheDocument()
})

test('the status card reports a running service', async () => {
  const body = { status: 'ok', service: 'Rozmarra API', version: '0.1.0', message: 'Running.' }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body))))
  renderApp()
  expect(await screen.findByText('Connected')).toBeInTheDocument()
  expect(screen.getByText(/The service version is 0\.1\.0\./)).toBeInTheDocument()
})

test('the doctor can switch the dashboard to Hindi', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('The service is not running.')))
  renderApp()
  await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
  expect(screen.getByRole('heading', { level: 1, name: 'रोज़मर्रा' })).toBeInTheDocument()
  expect(document.documentElement.lang).toBe('hi')
})
