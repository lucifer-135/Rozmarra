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
    await screen.findByText(
      'Rozmarra raised an alert. The chance of low glucose within the next 60 minutes has passed the alert level of 3.5%.',
    ),
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

const APPROVED_PLAN = {
  ...fixtures.plan,
  plan_name: 'Plan B: lower glimepiride with sargi',
  status: 'approved',
  approved_by: 'Meera Iyer',
  approved_on: '2026-10-13',
}

function mockApprovedPlan() {
  mockApi({
    '/api/patients/SY-0001': () => json({ language: 'hi' }),
    '/api/patients/SY-0001/plans': () =>
      json({ status: 'approved', plans: { 'plan-b': APPROVED_PLAN } }),
    '/api/patients/SY-0001/plans/plan-b/document': (url) =>
      new Response(url.searchParams.get('lang') === 'hi' ? 'हिन्दी संदेश' : 'English message'),
  })
}

test('an approved plan opens in English, even for a patient who reads Hindi', async () => {
  mockApprovedPlan()
  renderAt('/patients/SY-0001/plan')
  expect(
    await screen.findByText(/Approved by Dr Meera Iyer on 13 October 2026/),
  ).toBeInTheDocument()
  const frame = screen.getByTitle('Patient fasting plan in English')
  expect(frame).toHaveAttribute('src', '/api/patients/SY-0001/plans/plan-b/document?lang=en')
  expect(await screen.findByText('English message')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Print or save as PDF' })).toBeInTheDocument()

  const group = screen.getByRole('group', { name: 'Language of the patient plan' })
  await userEvent.click(within(group).getByRole('button', { name: 'हिन्दी' }))
  expect(screen.getByTitle('Patient fasting plan in हिन्दी')).toHaveAttribute(
    'src',
    '/api/patients/SY-0001/plans/plan-b/document?lang=hi',
  )
  expect(await screen.findByText('हिन्दी संदेश')).toBeInTheDocument()
})

test('a link with "?lang=hi" opens the approved plan in Hindi', async () => {
  mockApprovedPlan()
  renderAt('/patients/SY-0001/plan?lang=hi')
  expect(await screen.findByTitle('Patient fasting plan in हिन्दी')).toHaveAttribute(
    'src',
    '/api/patients/SY-0001/plans/plan-b/document?lang=hi',
  )
})

test('the model card screen explains the data and tests without a results table', async () => {
  mockApi({ '/api/model-card': () => json(sunday.model_card) })
  renderAt('/about')
  expect(await screen.findByText(/244 real meals of 86 patients/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Comparison with simpler methods' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Results and targets' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'What the results mean' })).not.toBeInTheDocument()
  // When a simpler method scores higher than the full model, the screen says so in words.
  expect(
    screen.getByText(/On simulated fasting days, the twin alone scored higher than the full model\./),
  ).toBeInTheDocument()
  expect(
    screen.getByText(
      /On real normal days, the model with CGM data only scored higher than the full model\./,
    ),
  ).toBeInTheDocument()
  expect(screen.getAllByText(/A random guess scores 0\.010\./).length).toBe(1)
  expect(screen.getAllByText(/A random guess scores 0\.011\./).length).toBe(1)
})
