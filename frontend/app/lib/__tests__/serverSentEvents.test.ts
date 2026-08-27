import { describe, expect, it } from 'vitest'
import { EventStreamParser } from '../serverSentEvents'

describe('EventStreamParser', () => {
  it('reads one payload per frame', () => {
    const parser = new EventStreamParser()
    expect(parser.push('data: {"stage":"batch"}\n\ndata: {"stage":"x"}\n\n')).toEqual([
      '{"stage":"batch"}',
      '{"stage":"x"}',
    ])
  })

  it('holds a frame back until the rest of it lands', () => {
    const parser = new EventStreamParser()

    expect(parser.push('data: {"stage":"ba')).toEqual([])
    expect(parser.push('tch","total":2}')).toEqual([])
    expect(parser.push('\n\n')).toEqual(['{"stage":"batch","total":2}'])
  })

  it('splits a chunk carrying several frames at once', () => {
    const parser = new EventStreamParser()
    const chunk = 'data: 1\n\ndata: 2\n\ndata: 3\n\n'
    expect(parser.push(chunk)).toEqual(['1', '2', '3'])
  })

  it('accepts a frame with no space after the colon', () => {
    const parser = new EventStreamParser()
    expect(parser.push('data:{"stage":"batch"}\n\n')).toEqual(['{"stage":"batch"}'])
  })

  it('joins a data field split over several lines', () => {
    const parser = new EventStreamParser()
    expect(parser.push('data: {\ndata: "a": 1\ndata: }\n\n')).toEqual(['{\n"a": 1\n}'])
  })

  it('skips a comment, which is how a keep-alive arrives', () => {
    const parser = new EventStreamParser()
    expect(parser.push(': keep-alive\n\ndata: 1\n\n')).toEqual(['1'])
  })

  it('skips fields other than data', () => {
    const parser = new EventStreamParser()
    expect(parser.push('event: message\nid: 4\ndata: 1\n\n')).toEqual(['1'])
  })

  it('treats CRLF line endings the same way', () => {
    const parser = new EventStreamParser()
    expect(parser.push('data: 1\r\n\r\ndata: 2\r\n\r\n')).toEqual(['1', '2'])
  })

  it('leaves an unterminated trailing frame unreported', () => {
    const parser = new EventStreamParser()
    expect(parser.push('data: 1\n\ndata: 2')).toEqual(['1'])
  })
})
