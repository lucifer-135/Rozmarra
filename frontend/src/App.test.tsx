import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import App from './App'
import i18n from './i18n'
import fixtures from './test/fixtures.json'

// The charts draw on a canvas, which the test browser does not have.
vi.mock('echarts-for-react/esm/core', () => ({ default: () => <div data-testid="chart" /> }))

type Handler = (body: unknown) => unknown

function mockApi(extra: Record<string, Handler> = {}) {
  const calls: { method: string; path: string; body: unknown }[] = []
  const routes: Record<string, Handler> = {
    'GET /api/health': () => ({ status: 'ok', service: 'Rozmarra API', version: '0.1.0' }),
    'GET /api/patients': () => fixtures.patients.map((p) => ({ ...p, plan_status: 'not_started' })),
    'GET /api/templates': () => fixtures.templates,
    'GET /api/plan-options': () => fixtures.options,
    'GET /api/patients/SY-0001/plans/default': () => fixtures.plan,
    'GET /api/patients/SY-0001/plans': () => ({ status: 'not_started', plans: {} }),
    'POST /api/patients/SY-0001/compare': (body) => {
      const { plan_a, plan_b } = body as { plan_a: object; plan_b: object }
      return {
        plan_a: { ...fixtures.simulation, plan: plan_a },
        plan_b: { ...fixtures.simulation, plan: plan_b },
      }
    },
    ...extra,
  }
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const path = input.split('?')[0]
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const handler = routes[`${method} ${path}`]
    if (!handler) return new Response(JSON.stringify({ detail: 'Not found.' }), { status: 404 })
    return new Response(JSON.stringify(handler(body)))
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
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

test('the patient list is sorted by risk and shows the notices on the screen', async () => {
  mockApi()
  renderAt('/patients')
  expect(await screen.findByRole('heading', { level: 1, name: 'Patients who plan to fast' }))
  const rows = await screen.findAllByRole('row')
  // The first row holds the column headings. The API sends the rows sorted by risk.
  expect(within(rows[1]).getByText('Ramesh Patel, Age 62')).toBeInTheDocument()
  expect(within(rows[2]).getByText('Sunita Sharma, Age 54')).toBeInTheDocument()
  expect(within(rows[1]).getByText('7% (Low)')).toBeInTheDocument()
  expect(within(rows[2]).getByText('Dehydration caution')).toBeInTheDocument()
  expect(within(rows[2]).getByText('Not started')).toBeInTheDocument()
  expect(
    screen.getByText(
      'Rozmarra supports clinical decisions. It does not replace the judgement of a doctor.',
    ),
  ).toBeInTheDocument()
  expect(screen.getAllByText('Synthetic data').length).toBeGreaterThan(0)
  expect(await screen.findByText(/The service version is 0\.1\.0\./)).toBeInTheDocument()
})

test('the dashboard reports when the service is not running', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('The service is not running.')))
  renderAt('/patients')
  expect(await screen.findByText(/cannot reach the Rozmarra service/)).toBeInTheDocument()
})

test('the doctor can switch the dashboard to Hindi', async () => {
  mockApi()
  renderAt('/patients')
  await screen.findByText('Ramesh Patel, Age 62')
  await userEvent.click(screen.getByRole('button', { name: 'हिन्दी' }))
  expect(screen.getByRole('heading', { level: 1, name: 'उपवास रखने वाले मरीज़' })).toBeInTheDocument()
  expect(screen.getByText('Ramesh Patel, उम्र 62')).toBeInTheDocument()
  expect(document.documentElement.lang).toBe('hi')
})

test('the simulator compares two plans and saves them when the doctor tests them', async () => {
  const calls = mockApi({
    'PUT /api/patients/SY-0001/plans/plan-a': (body) => body,
    'PUT /api/patients/SY-0001/plans/plan-b': (body) => body,
  })
  renderAt('/patients/SY-0001/simulator')
  expect(await screen.findByText(/With Plan A, the predicted lowest glucose is/)).toBeInTheDocument()
  expect(screen.getByRole('table', { name: /compares the two plans/ })).toBeInTheDocument()
  expect(screen.getAllByText('Dehydration caution').length).toBeGreaterThan(0)
  // The first comparison runs when the screen opens and does not save anything.
  expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(0)

  // The doctor lowers the glimepiride dose in Plan B.
  await userEvent.click(screen.getByRole('tab', { name: /Plan B/ }))
  const panel = screen.getByRole('tabpanel')
  const dose = within(panel).getByLabelText('Dose, Glimepiride')
  await userEvent.clear(dose)
  await userEvent.type(dose, '1')
  expect(await screen.findByText(/The plans have changed since the last test/)).toBeInTheDocument()
  for (const button of screen.getAllByRole('button', { name: /Approve this plan/ })) {
    expect(button).toBeDisabled()
  }

  await userEvent.click(screen.getByRole('button', { name: 'Test and compare both plans' }))
  await waitFor(() => expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(2))
  const compare = calls.filter((c) => c.path.endsWith('/compare')).at(-1)!
  const planB = (compare.body as { plan_b: { medicines: { name: string; dose: number }[] } })
    .plan_b
  expect(planB.medicines.find((m) => m.name === 'glimepiride')?.dose).toBe(1)
  expect(screen.queryByText(/The plans have changed since the last test/)).not.toBeInTheDocument()
})

test('a dose above the largest single dose stops the test', async () => {
  mockApi()
  renderAt('/patients/SY-0001/simulator')
  await screen.findByText(/With Plan A, the predicted lowest glucose is/)
  const dose = within(screen.getByRole('tabpanel')).getByLabelText('Dose, Glimepiride')
  await userEvent.clear(dose)
  await userEvent.type(dose, '40')
  expect(
    await screen.findByText(/above the largest single dose that Rozmarra accepts \(8 mg\)/),
  ).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Test and compare both plans' })).toBeDisabled()
})

test('the doctor approves a tested plan with a name', async () => {
  mockApi({
    'POST /api/patients/SY-0001/plans/plan-b/approve': (body) => {
      const { plan, doctor_name } = body as { plan: object; doctor_name: string }
      return {
        plan: { ...plan, status: 'approved', approved_by: doctor_name, approved_on: '2026-10-13' },
        approval_text: `Approved by Dr ${doctor_name} on 13 October 2026`,
      }
    },
  })
  renderAt('/patients/SY-0001/simulator')
  await screen.findByText(/With Plan A, the predicted lowest glucose is/)
  await userEvent.click(screen.getByRole('button', { name: /Approve this plan \(Plan B/ }))
  const dialog = await screen.findByRole('dialog')
  const confirm = within(dialog).getByRole('button', { name: 'Approve the plan' })
  expect(confirm).toBeDisabled()
  await userEvent.type(within(dialog).getByLabelText('Name of the doctor'), 'Meera Iyer')
  await userEvent.click(confirm)
  expect(await screen.findByText('Approved by Dr Meera Iyer on 13 October 2026')).toBeInTheDocument()
})
