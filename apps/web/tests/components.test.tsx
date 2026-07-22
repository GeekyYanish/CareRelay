import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusPill } from '../src/components/StatusPill'
import { UncertaintyMap } from '../src/components/UncertaintyMap'

describe('clinical safety components', () => {
  it('pairs emergency color with visible text', () => {
    render(<StatusPill urgency="Emergency" />)
    expect(screen.getByText('Emergency')).toBeVisible()
  })

  it('renders uncertainty as labels and counts', () => {
    render(<UncertaintyMap map={{known_facts:['fact'],missing_facts:['onset'],contradictions:[],red_flags:[],retrieval_quality:.82,uncertainty:.18}} />)
    expect(screen.getByText('82% evidence quality')).toBeVisible()
    expect(screen.getByText('Missing facts')).toBeVisible()
    expect(screen.getByText('Model uncertainty:', {exact:false})).toBeVisible()
  })
})

