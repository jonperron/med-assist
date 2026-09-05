import { describe, expect, it } from 'vitest'
import { unsecuredDeployment } from '../deployment'

describe('unsecuredDeployment', () => {
  it('is off when the variable is not set', () => {
    // The default is the local deployment, where the warning would be noise:
    // the only caller is the person at the keyboard.
    expect(unsecuredDeployment(undefined)).toBe(false)
  })

  it('is off when the variable is set to nothing', () => {
    // A Compose passthrough with nothing behind it arrives as the empty string.
    expect(unsecuredDeployment('')).toBe(false)
    expect(unsecuredDeployment('   ')).toBe(false)
  })

  it.each(['1', 'true', 'yes', 'on', 'TRUE', ' On '])('reads %s as on', raw => {
    expect(unsecuredDeployment(raw)).toBe(true)
  })

  it.each(['0', 'false', 'no', 'off', 'OFF'])('reads %s as off', raw => {
    // The point of the explicit off-list. Treating every non-empty value as on
    // would turn `UNSECURED_DEPLOYMENT=false` into a warning on every screen,
    // and an operator who saw that would reach for deleting the variable rather
    // than trusting it.
    expect(unsecuredDeployment(raw)).toBe(false)
  })

  it.each(['maybe', 'oui', 'y', 'enabled', 'ture'])('reads %s as on', raw => {
    // A set-but-unrecognised value is an operator who has already decided the
    // deployment is public and misspelled the switch. Reading it as off would
    // drop the only warning a clinician gets and restore a badge claiming the
    // documents stay on their machine, silently. Reading it as on shows a
    // banner nobody quite asked for. Only one of those is a bad outcome.
    expect(unsecuredDeployment(raw)).toBe(true)
  })
})
