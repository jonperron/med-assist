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

  it.each(['0', 'false', 'no', 'off'])('reads %s as off', raw => {
    // The point of an explicit list. Treating any non-empty value as true would
    // turn `UNSECURED_DEPLOYMENT=false` into a warning on every screen, and an
    // operator who saw that would reach for deleting the variable rather than
    // trusting it.
    expect(unsecuredDeployment(raw)).toBe(false)
  })

  it('does not read an unrecognised value as on', () => {
    expect(unsecuredDeployment('maybe')).toBe(false)
  })
})
