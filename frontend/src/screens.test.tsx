import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import App from './App'
import i18n from './i18n'
import fixtures from './test/fixtures.json'
import sunday from './test/fixtures_sunday.json'

// Tests for screens 4 to 6: the live fasting monitor, the patient plan and the model card.

vi.mock('echarts-for-react/esm/core', () => ({ default: () => <div data-testid="chart" /> }))

type Handler = (url: URL) => Response

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: string) => {
    const url = new URL(input, 'http://localhost')
    const common: Record<string, Handler> = {
      '/api/health': () => json({ status: 'ok', service: 'Rozmarra API', version: '0.1.0' }),
      '/api/patients': () => json(fixtures.patients),
      '/api/templates': () => json(fixtures.templates),
      '/api/plan-options': () => json(fixtures.options),
    }
    const handler = routes[url.pathname] ?? common[url.pathname]
    return handler ? handler(url) : json({ detail: 'Not found.' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18n.changeLanguage('en')
})

test('the live fasting monitor jumps to the next alert and shows the reasons', async () => {
  const fetchMock = mockApi({
    '/api/patients/SY-0002/replay': (url) => {
      const at = url.searchParams.get('at')
      if (!at) return json(sunday.overview)
      return json(at === sunday.overview.alerts[0].time ? sunday.moment : sunday.quiet)
    },
  })
  renderAt('/patients/SY-0002/monitor')
  expect(await screen.findByText('No alert at this moment.')).toBeInTheDocument()
  expect(screen.getByRole('slider', { name: 'Time in the recorded fasting day' })).toHaveAttribute(
    'aria-valuetext',
    '8:00 pm on 14 October 2026',
  )

  await userEvent.click(screen.getByRole('button', { name: 'Go to the next alert' }))
  expect(
    await screen.findByText('Low glucose is likely within the next 60 minutes.'),
  ).toBeInTheDocument()
  expect(screen.getByText('9% (Moderate)')).toBeInTheDocument()
  expect(screen.getByText(sunday.moment.reasons[0].en)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /10:50 am: 9%/ })).toBeInTheDocument()
  const asked = fetchMock.mock.calls.map(([input]) => String(input))
  expect(asked.some((u) => u.includes('at=2026-10-15T10%3A50'))).toBe(true)
})

test('the patient plan screen asks for an approval first', async () => {
  mockApi({
    '/api/patients/SY-0001': () => json({ language: 'hi' }),
    '/api/patients/SY-0001/plans': () => json({ status: 'draft', plans: {} }),
  })
  renderAt('/patients/SY-0001/plan')
  expect(await screen.findByText('No plan is approved yet.')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Go to the screen/ })).toHaveAttribute(
    'href',
    '/patients/SY-0001/simulator',
  )
})

test('an approved plan opens in the patient language with the short message', async () => {
  const approved = {
    ...fixtures.plan,
    plan_name: 'Plan B: lower glimepiride with sargi',
    status: 'approved',
    approved_by: 'Meera Iyer',
    approved_on: '2026-10-13',
  }
  mockApi({
    '/api/patients/SY-0001': () => json({ language: 'hi' }),
    '/api/patients/SY-0001/plans': () => json({ status: 'approved', plans: { 'plan-b': approved } }),
    '/api/patients/SY-0001/plans/plan-b/document': (url) =>
      new Response(url.searchParams.get('lang') === 'hi' ? 'हिन्दी संदेश' : 'English message'),
  })
  renderAt('/patients/SY-0001/plan')
  expect(
    await screen.findByText(/Approved by Dr Meera Iyer on 13 October 2026/),
  ).toBeInTheDocument()
  const frame = screen.getByTitle('Patient fasting plan in हिन्दी')
  expect(frame).toHaveAttribute('src', '/api/patients/SY-0001/plans/plan-b/document?lang=hi')
  expect(await screen.findByText('हिन्दी संदेश')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Print or save as PDF' })).toBeInTheDocument()

  const group = screen.getByRole('group', { name: 'Language of the patient plan' })
  await userEvent.click(within(group).getByRole('button', { name: 'English' }))
  expect(screen.getByTitle('Patient fasting plan in English')).toHaveAttribute(
    'src',
    '/api/patients/SY-0001/plans/plan-b/document?lang=en',
  )
  expect(await screen.findByText('English message')).toBeInTheDocument()
})

test('the model card screen reports every target honestly', async () => {
  mockApi({ '/api/model-card': () => json(sunday.model_card) })
  renderAt('/about')
  const table = await screen.findByRole('table', { name: /AUROC shows how well/ })
  const falseAlerts = within(table).getByText(/False alerts per patient per fasting day/).closest('tr')!
  expect(within(falseAlerts).getByText('Not met')).toBeInTheDocument()
  const real = within(table).getByText(/real normal days \(AUROC\)/).closest('tr')!
  expect(within(real).getByText(/0\.943 \(95% interval 0\.919 to 0\.964\)/)).toBeInTheDocument()
  expect(within(real).getByText('Met')).toBeInTheDocument()
  expect(within(table).getByText('Not tested yet')).toBeInTheDocument()
  expect(screen.getByText(/the twin alone scored a higher AUPRC \(0\.554\)/)).toBeInTheDocument()
})
