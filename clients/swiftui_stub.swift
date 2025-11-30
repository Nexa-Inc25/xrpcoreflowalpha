import SwiftUI

// MARK: - Models matching /ui JSON shape

struct EventFeatures: Decodable {
    let txHash: String?
    let usdValue: Double?
}

struct EventItem: Decodable, Identifiable {
    let id: String
    let timestamp: String
    let message: String
    let type: String
    let confidence: String
    let network: String?
    let ruleScore: Double?
    let features: EventFeatures?
}

struct FlowsResponse: Decodable {
    let page: Int
    let pageSize: Int
    let total: Int
    let items: [EventItem]
}

struct SubscriptionOption: Decodable, Identifiable {
    let id = UUID()
    let tier: String
    let price: String
    let action: String
}

struct DashboardChild: Decodable, Identifiable {
    let id = UUID()
    let type: String

    // Header
    let title: String?
    let subtitle: String?

    // LiveCounter
    let label: String?
    let value: Int?

    // EventList
    let events: [EventItem]?

    // PredictiveBanner / UpgradeBanner / Footer / ReplayButton
    let text: String?
    let visible: Bool?
    let action: String?
    let endpoint: String?

    // ImpactForecastCard
    let symbol: String?
    let inferredUsdM: Double?
    let buyImpact: Double?
    let sellImpact: Double?
    let depth1pctMm: Double?
    let blur: Bool?
    let cta: String?

    // SubscriptionCard
    let options: [SubscriptionOption]?
    let cryptoQr: Bool?
}

struct DashboardRoot: Decodable {
    let type: String
    let spacing: Int?
    let children: [DashboardChild]
}

// MARK: - Main SwiftUI view

struct SDUIFeedView: View {
    @State private var root: DashboardRoot?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var events: [EventItem] = []
    @State private var lastEventId: String?
    @State private var isConnected = false
    @State private var wsTask: URLSessionWebSocketTask?

    private let baseURL = URL(string: "http://localhost:8000")!

    var body: some View {
        NavigationView {
            Group {
                if let root = root {
                    ScrollView {
                        VStack(alignment: .leading, spacing: CGFloat(root.spacing ?? 20)) {
                            ForEach(root.children) { child in
                                childView(child)
                            }
                        }
                        .padding()
                    }
                } else if isLoading {
                    ProgressView("Loading dashboard…")
                } else if let errorMessage = errorMessage {
                    VStack(spacing: 8) {
                        Text("Failed to load /ui")
                            .font(.headline)
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding()
                } else {
                    Text("No data")
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("DarkFlow Tracker")
        }
        .task { await loadDashboard() }
        .onAppear { connectWebSocketIfNeeded() }
    }

    // MARK: - Networking

    func loadDashboard() async {
        let url = baseURL.appendingPathComponent("ui")
        isLoading = true
        errorMessage = nil
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let decoded = try decoder.decode(DashboardRoot.self, from: data)
            await MainActor.run {
                self.root = decoded
                if self.events.isEmpty {
                    if let listChild = decoded.children.first(where: { $0.type == "EventList" }) {
                        self.events = listChild.events ?? []
                    }
                }
                self.isLoading = false
            }
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    // MARK: - Rendering helpers

    @ViewBuilder
    func childView(_ child: DashboardChild) -> some View {
        switch child.type {
        case "Header":
            VStack(alignment: .leading, spacing: 4) {
                Text(child.title ?? "DarkFlow Tracker")
                    .font(.title2)
                    .bold()
                if let subtitle = child.subtitle {
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }

        case "LiveCounter":
            HStack {
                Text(child.label ?? "Events")
                    .font(.headline)
                Spacer()
                Text("\(child.value ?? 0)")
                    .font(.system(.headline, design: .monospaced))
            }
            .padding(10)
            .background(Color.gray.opacity(0.12))
            .cornerRadius(10)

        case "EventList":
            let sourceEvents = events.isEmpty ? (child.events ?? []) : events
            VStack(alignment: .leading, spacing: 8) {
                Text("Recent Events")
                    .font(.headline)
                ForEach(sourceEvents) { event in
                    NavigationLink(
                        destination: FlowDetailView(baseURL: baseURL, txHash: event.features?.txHash ?? "")
                    ) {
                        eventRow(event)
                    }
                    .simultaneousGesture(TapGesture().onEnded {
                        if event.confidence.lowercased() == "high" {
                            prefetchFlows(for: event.features?.txHash)
                        }
                    })
                }
            }

        case "PredictiveBanner":
            if child.visible ?? false {
                Text(child.text ?? "High-volume flow detected")
                    .font(.subheadline)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.orange.opacity(0.15))
                    .cornerRadius(10)
            }

        case "ImpactForecastCard":
            impactForecastCard(child)

        case "UpgradeBanner":
            Text(child.text ?? "Unlock real-time Impact Forecasts")
                .font(.callout)
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.purple.opacity(0.15))
                .cornerRadius(10)

        case "SubscriptionCard":
            subscriptionCard(child)

        case "ReplayButton":
            if let text = child.text {
                Button(text) {
                    // In a full app, open child.endpoint as a deep link or in-app replay.
                }
                .buttonStyle(.bordered)
            }

        case "Footer":
            Text(child.text ?? "Real-time • Public data only")
                .font(.footnote)
                .foregroundColor(.secondary)
                .padding(.top, 8)

        default:
            EmptyView()
        }
    }

    @ViewBuilder
    func eventRow(_ event: EventItem) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(event.message)
                .font(.subheadline)
            HStack(spacing: 8) {
                Text(event.type.uppercased())
                    .font(.caption2)
                    .foregroundColor(.secondary)
                Text(event.confidence.capitalized)
                    .font(.caption2)
                    .foregroundColor(confidenceColor(event.confidence))
                if let net = event.network {
                    Text(net.capitalized)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                if let usd = event.features?.usdValue, usd > 0 {
                    Text(String(format: "~$%.1fm", usd / 1_000_000))
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding(8)
        .background(Color.gray.opacity(0.1))
        .cornerRadius(8)
    }

    @ViewBuilder
    func impactForecastCard(_ child: DashboardChild) -> some View {
        let content = VStack(alignment: .leading, spacing: 6) {
            Text("Impact Forecast (") + Text(child.symbol ?? "ETHUSDT") + Text(")")
                .font(.headline)
            if let usdM = child.inferredUsdM {
                Text(String(format: "Inferred notional: %.1fM USD", usdM))
                    .font(.subheadline)
            }
            HStack(spacing: 12) {
                if let buy = child.buyImpact {
                    Text(String(format: "Buy impact: %.2f%%", buy))
                        .font(.caption)
                }
                if let sell = child.sellImpact {
                    Text(String(format: "Sell impact: %.2f%%", sell))
                        .font(.caption)
                }
            }
            if let depth = child.depth1pctMm {
                Text(String(format: "Depth @1%%: %.1fM", depth))
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            if child.blur == true, let cta = child.cta {
                Text(cta)
                    .font(.caption)
                    .foregroundColor(.purple)
                    .padding(.top, 4)
            }
        }
        .padding(10)

        if child.blur == true {
            content
                .blur(radius: 4)
                .background(Color.gray.opacity(0.12))
                .cornerRadius(10)
        } else if child.visible ?? true {
            content
                .background(Color.gray.opacity(0.12))
                .cornerRadius(10)
        } else {
            EmptyView()
        }
    }

    @ViewBuilder
    func subscriptionCard(_ child: DashboardChild) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(child.title ?? "Unlock Real-Time Dark Flow Intelligence")
                .font(.headline)
            if let options = child.options {
                ForEach(options) { opt in
                    HStack {
                        Text(opt.tier.uppercased())
                            .font(.caption)
                            .padding(4)
                            .background(Color.gray.opacity(0.2))
                            .cornerRadius(4)
                        Text(opt.price)
                            .font(.subheadline)
                        Spacer()
                    }
                }
            }
            if child.cryptoQr == true {
                Text("Crypto QR available")
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
        .padding(10)
        .background(Color.gray.opacity(0.12))
        .cornerRadius(10)
    }

    func confidenceColor(_ bucket: String) -> Color {
        switch bucket.lowercased() {
        case "high": return .red
        case "medium": return .orange
        default: return .green
        }
    }

    // MARK: - WebSocket live events

    func connectWebSocketIfNeeded() {
        if isConnected { return }
        connectWebSocket()
    }

    func connectWebSocket() {
        var components = URLComponents(url: baseURL.appendingPathComponent("events"), resolvingAgainstBaseURL: false)
        components?.scheme = (baseURL.scheme == "https" ? "wss" : "ws")
        guard let url = components?.url else { return }

        let task = URLSession.shared.webSocketTask(with: url)
        wsTask = task
        task.resume()
        isConnected = true
        receiveWebSocketMessage()
    }

    func receiveWebSocketMessage() {
        wsTask?.receive { result in
            switch result {
            case .success(let message):
                if case .string(let text) = message,
                   let data = text.data(using: .utf8) {
                    let decoder = JSONDecoder()
                    decoder.keyDecodingStrategy = .convertFromSnakeCase
                    if let evt = try? decoder.decode(EventItem.self, from: data) {
                        DispatchQueue.main.async {
                            if evt.id != self.lastEventId {
                                self.events.insert(evt, at: 0)
                                self.lastEventId = evt.id
                            }
                        }
                    }
                }
                // Continue listening
                receiveWebSocketMessage()

            case .failure:
                DispatchQueue.main.async {
                    self.isConnected = false
                    self.wsTask = nil
                }
            }
        }
    }
}

final class FlowsCache {
    static let shared = FlowsCache()

    private var storage: [String: FlowsResponse] = [:]
    private let queue = DispatchQueue(label: "FlowsCache.storage")

    func get(for txHash: String) -> FlowsResponse? {
        queue.sync {
            storage[txHash.lowercased()]
        }
    }

    func store(_ response: FlowsResponse, for txHash: String) {
        let key = txHash.lowercased()
        queue.async {
            self.storage[key] = response
        }
    }
}

struct FlowDetailView: View {
    let baseURL: URL
    let txHash: String

    @State private var flows: FlowsResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var isPremium = true
    @State private var predictedClose: Double?
    @State private var isLoadingForecast = false
    @State private var forecastError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if isLoading {
                ProgressView("Loading flow details…")
            } else if let flows = flows, !flows.items.isEmpty {
                Text("Flow Details")
                    .font(.title2)
                Text(txHash)
                    .font(.footnote)
                    .foregroundColor(.secondary)
                Text("Total matches: \(flows.total)")
                    .font(.subheadline)
                ForEach(flows.items) { item in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(item.message)
                            .font(.subheadline)
                        HStack(spacing: 8) {
                            Text(item.type.uppercased())
                                .font(.caption2)
                                .foregroundColor(.secondary)
                            Text(item.confidence.capitalized)
                                .font(.caption2)
                                .foregroundColor(confidenceColor(item.confidence))
                            if let net = item.network {
                                Text(net.capitalized)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                        if let usd = item.features?.usdValue, usd > 0 {
                            Text(String(format: "USD value: $%.2f", usd))
                                .font(.caption)
                        }
                        if let score = item.ruleScore {
                            Text(String(format: "Rule score: %.1f", score))
                                .font(.caption)
                                .blur(radius: isPremium ? 0 : 4)
                        }
                    }
                    .padding(8)
                    .background(Color.gray.opacity(0.08))
                    .cornerRadius(8)
                }
                // Forecast section
                if isLoadingForecast {
                    ProgressView("Fetching ETH forecast…")
                } else if let pred = predictedClose {
                    let txt = Text(String(format: "Predicted ETH close: $%.2f", pred))
                        .font(.caption)
                        .foregroundColor(.secondary)
                    if isPremium {
                        txt
                    } else {
                        txt
                            .blur(radius: 4)
                            .overlay {
                                Button("Upgrade for clear forecast") {
                                    // Upgrade CTA hook
                                }
                                .buttonStyle(.borderedProminent)
                            }
                    }
                } else if let fErr = forecastError {
                    Text("Forecast error: \(fErr)")
                        .font(.caption2)
                        .foregroundColor(.red)
                }
            } else if let errorMessage = errorMessage {
                Text("Failed to load flow details")
                    .font(.headline)
                Text(errorMessage)
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Text("No matching flows")
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .navigationTitle("Flow")
        .task {
            await loadFlows()
            await loadForecast()
        }
    }

    func loadFlows() async {
        if let cached = FlowsCache.shared.get(for: txHash), cached.total > 0 {
            await MainActor.run {
                self.flows = cached
            }
            return
        }
        isLoading = true
        errorMessage = nil
        var components = URLComponents(url: baseURL.appendingPathComponent("flows"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "tx_hash", value: txHash),
            URLQueryItem(name: "page_size", value: "10")
        ]
        guard let url = components?.url else {
            await MainActor.run {
                self.isLoading = false
                self.errorMessage = "invalid_url"
            }
            return
        }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let decoded = try decoder.decode(FlowsResponse.self, from: data)
            await MainActor.run {
                self.flows = decoded
                self.isLoading = false
            }
            FlowsCache.shared.store(decoded, for: txHash)
        } catch {
            await MainActor.run {
                self.errorMessage = error.localizedDescription
                self.isLoading = false
            }
        }
    }

    func loadForecast() async {
        isLoadingForecast = true
        forecastError = nil
        do {
            // Step 1: fetch latest ETH OHLCV
            let ohlcvURL = baseURL.appendingPathComponent("analytics/eth_ohlcv_latest")
            let (ohlcvData, _) = try await URLSession.shared.data(from: ohlcvURL)
            let ohlcv = try JSONDecoder().decode([String: Double].self, from: ohlcvData)
            guard let open = ohlcv["open"],
                  let high = ohlcv["high"],
                  let low = ohlcv["low"],
                  let volume = ohlcv["volume"] else {
                throw NSError(domain: "missing_ohlcv", code: 1)
            }
            // Step 2: call /analytics/eth_close_forecast
            var comps = URLComponents(url: baseURL.appendingPathComponent("analytics/eth_close_forecast"), resolvingAgainstBaseURL: false)
            comps?.queryItems = [
                URLQueryItem(name: "open", value: String(open)),
                URLQueryItem(name: "high", value: String(high)),
                URLQueryItem(name: "low", value: String(low)),
                URLQueryItem(name: "volume", value: String(volume)),
            ]
            guard let url = comps?.url else {
                throw NSError(domain: "invalid_url", code: 2)
            }
            let (forecastData, _) = try await URLSession.shared.data(from: url)
            let forecast = try JSONDecoder().decode([String: Double].self, from: forecastData)
            await MainActor.run {
                self.predictedClose = forecast["predicted_close"]
                self.isLoadingForecast = false
            }
        } catch {
            await MainActor.run {
                self.forecastError = error.localizedDescription
                self.isLoadingForecast = false
            }
        }
    }
}

extension SDUIFeedView {
    func prefetchFlows(for txHash: String?) {
        guard let txHash = txHash, !txHash.isEmpty else { return }
        if FlowsCache.shared.get(for: txHash) != nil {
            return
        }
        var components = URLComponents(url: baseURL.appendingPathComponent("flows"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "tx_hash", value: txHash),
            URLQueryItem(name: "page_size", value: "10")
        ]
        guard let url = components?.url else { return }
        URLSession.shared.dataTask(with: url) { data, _, _ in
            guard let data = data else { return }
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            if let decoded = try? decoder.decode(FlowsResponse.self, from: data) {
                FlowsCache.shared.store(decoded, for: txHash)
            }
        }.resume()
    }
}
