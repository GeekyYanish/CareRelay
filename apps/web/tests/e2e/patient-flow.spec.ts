import {mkdirSync} from 'node:fs'
import {resolve} from 'node:path'
import {expect, test, type Page} from '@playwright/test'

const artifactDir = resolve(process.cwd(), '../../artifacts/browser')
mkdirSync(artifactDir, {recursive:true})

async function login(page: Page, role: 'patient'|'clinician'|'reviewer'|'admin' = 'patient') {
  await page.goto('/login')
  if (role !== 'patient') {
    const label = {clinician:'Clinical workspace', reviewer:'Review escalations', admin:'Safety operations'}[role]
    await page.getByRole('button', {name:new RegExp(label)}).click()
  }
  await page.getByRole('button', {name:/Enter CareRelay/}).click()
  await expect(page).toHaveURL(new RegExp(`/${role}`))
}

const scenarios = [
  ['Emergency red flag', 'Seek emergency help now', 'DETERMINISTIC_RED_FLAG'],
  ['Deterministic Same-Day', 'Qualified review is needed today', 'DETERMINISTIC_RED_FLAG'],
  ['Self-Care agreement', 'Monitor and use the safety net', 'TWO_KEY_APPROVED'],
  ['Routine agreement', 'Arrange routine professional review', 'TWO_KEY_APPROVED'],
  ['Critic disagreement', 'Qualified review is needed today', 'AGENT_DISAGREEMENT'],
  ['Missing critical facts', 'Qualified review is needed today', 'MISSING_CRITICAL_FACT'],
  ['Low retrieval quality', 'Qualified review is needed today', 'LOW_RETRIEVAL_QUALITY'],
  ['Provider timeout', 'Qualified review is needed today', 'PROCESSING_TIMEOUT'],
] as const

for (const [scenario, title, reason] of scenarios) {
  test(`${scenario} reaches the expected gated guidance`, async ({page}) => {
    await login(page)
    await page.getByRole('button', {name:new RegExp(scenario)}).click()
    await expect(page.getByRole('heading', {name:title})).toBeVisible()
    await expect(page.getByText(reason, {exact:true})).toBeVisible()
    await expect(page.getByText('Evidence used')).toBeVisible()
    if (scenario === 'Emergency red flag') {
      await expect(page.getByText(/Contact your local emergency service now/)).toBeVisible()
      await page.screenshot({path:resolve(artifactDir, 'patient-emergency-desktop.png'), fullPage:true})
    }
  })
}

test('patient handoff continues through clinician, reviewer, and admin roles', async ({page}) => {
  await login(page)
  await page.getByRole('button', {name:/Emergency red flag/}).click()
  await expect(page.getByRole('heading', {name:'Seek emergency help now'})).toBeVisible()
  await page.getByRole('button', {name:'Sign out'}).click()

  await login(page, 'clinician')
  await expect(page.getByRole('heading', {name:'SOAP with sentence provenance'})).toBeVisible()
  await page.getByRole('button', {name:/Sign draft/}).click()
  await expect(page.getByText('signed', {exact:true})).toBeVisible()
  await page.getByRole('button', {name:'Sign out'}).click()

  await login(page, 'reviewer')
  const openCase = page.locator('.escalation-list article').filter({has:page.getByText('open', {exact:true})}).first()
  await openCase.getByRole('button', {name:'Claim case'}).click()
  const claimedCase = page.locator('.escalation-list article').filter({has:page.getByText('claimed', {exact:true})}).first()
  await claimedCase.getByLabel('Resolution note').fill('Reviewed and handed off in the demonstration workflow.')
  await claimedCase.getByRole('button', {name:/Resolve with audit note/}).click()
  await expect(page.getByText(/Reviewed and handed off/).first()).toBeVisible()
  await page.getByRole('button', {name:'Sign out'}).click()

  await login(page, 'admin')
  await expect(page.getByRole('heading', {name:'System evidence, not theatre.'})).toBeVisible()
  await expect(page.getByText('local-mock-mcp')).toBeVisible()
  await page.screenshot({path:resolve(artifactDir, 'admin-desktop.png'), fullPage:true})
})

test('mobile patient intake is usable at 375px', async ({page}) => {
  await page.setViewportSize({width:375, height:812})
  await login(page)
  await expect(page.getByRole('heading', {name:/Tell us what’s happening/})).toBeVisible()
  await page.screenshot({path:resolve(artifactDir, 'patient-intake-mobile.png'), fullPage:true})
})
