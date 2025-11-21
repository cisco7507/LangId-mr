import { render, screen, waitFor, renderHook } from '@testing-library/react';
import { useClusterMetricsSummary } from '../hooks/useClusterMetricsSummary';
import ClusterMetricsCard from '../components/ClusterMetricsCard';
import { apiFetch } from '../api';

// Mock apiFetch
jest.mock('../api', () => ({
    apiFetch: jest.fn(),
}));

describe('useClusterMetricsSummary', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('fetches data successfully', async () => {
        const mockData = {
            nodes: [
                { name: 'node-a', up: true, jobs_owned_total: 10, jobs_active: 1, jobs_submitted_as_target: 5, last_health_ts: 1000 }
            ]
        };
        apiFetch.mockResolvedValue({
            ok: true,
            json: async () => mockData,
        });

        const { result } = renderHook(() => useClusterMetricsSummary());

        expect(result.current.loading).toBe(true);
        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.data).toEqual(mockData);
        expect(result.current.error).toBeNull();
    });

    it('handles fetch error', async () => {
        apiFetch.mockRejectedValue(new Error('Network error'));

        const { result } = renderHook(() => useClusterMetricsSummary());

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.error).toBeTruthy();
    });
});

describe('ClusterMetricsCard', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    it('renders loading state', () => {
        // Mock hook to return loading
        jest.spyOn(require('../hooks/useClusterMetricsSummary'), 'useClusterMetricsSummary').mockReturnValue({
            data: null,
            loading: true,
            error: null,
            lastUpdated: null,
        });

        const { container } = render(<ClusterMetricsCard />);
        expect(container.querySelector('.animate-pulse')).toBeTruthy();
    });

    it('renders error state', () => {
        jest.spyOn(require('../hooks/useClusterMetricsSummary'), 'useClusterMetricsSummary').mockReturnValue({
            data: null,
            loading: false,
            error: new Error('Failed'),
            lastUpdated: null,
        });

        render(<ClusterMetricsCard />);
        expect(screen.getByText('Cluster Metrics Unavailable')).toBeTruthy();
    });

    it('renders nodes data', () => {
        const mockData = {
            nodes: [
                { name: 'node-a', up: true, jobs_owned_total: 10, jobs_active: 1, jobs_submitted_as_target: 5, last_health_ts: 1600000000 }
            ]
        };
        jest.spyOn(require('../hooks/useClusterMetricsSummary'), 'useClusterMetricsSummary').mockReturnValue({
            data: mockData,
            loading: false,
            error: null,
            lastUpdated: new Date(),
        });

        render(<ClusterMetricsCard />);
        expect(screen.getByText('node-a')).toBeTruthy();
        expect(screen.getByText('UP')).toBeTruthy();
        expect(screen.getByText('10')).toBeTruthy(); // Owned
    });
});
