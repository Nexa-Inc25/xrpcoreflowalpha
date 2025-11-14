import SwiftUI

struct SDUIComponent: Decodable {
    let type: String
    let id: String
    let title: String?
    let urgency: String?
    let color: String?
    let summary: String?
    let time_delta: String?
    let confidence: Int?
    let predicted_impact: String?
    let auto_expand: Bool?
}

struct SDUIFeed: Decodable {
    let feed: [SDUIPayload]
    let updated_at: String
}

struct SDUIPayload: Decodable {
    let layout_version: String
    let timestamp: String
    let components: [SDUIComponent]
}

struct SDUICard: View {
    let component: SDUIComponent
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let title = component.title { Text(title).font(.headline) }
            if let summary = component.summary { Text(summary).font(.subheadline) }
            HStack {
                if let conf = component.confidence { Text("Conf: \(conf)%") }
                if let imp = component.predicted_impact { Text(imp) }
            }
        }
        .padding()
        .background(Color.gray.opacity(0.1))
        .cornerRadius(12)
    }
}

struct SDUIFeedView: View {
    @State private var payloads: [SDUIPayload] = []

    var body: some View {
        ScrollView {
            ForEach(payloads, id: \.timestamp) { p in
                ForEach(p.components, id: \.id) { c in
                    SDUICard(component: c)
                        .padding(.horizontal)
                        .padding(.vertical, 4)
                }
            }
        }
        .task { await loadFeed() }
    }

    func loadFeed() async {
        guard let url = URL(string: "http://localhost:8000/sdui/feed") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoded = try JSONDecoder().decode(SDUIFeed.self, from: data)
            payloads = decoded.feed
        } catch {
            print("SDUI fetch error:", error.localizedDescription)
        }
    }
}
