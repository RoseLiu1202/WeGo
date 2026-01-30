//
//  Embeddedpollview.swift
//  WeGo
//
//  Created by Rose Liu on 10/25/25.
//

import UIKit

// MARK: - Embedded Poll Message (Display Only)
class EmbeddedPollView: UIView {
    
    // MARK: - Properties
    private let pollOptions = [
        "1️⃣ Mexican",
        "2️⃣ Thai",
        "3️⃣ Fast food",
        "4️⃣ Chinese"
    ]
    
    // MARK: - UI Elements
    private let containerView: UIView = {
        let v = UIView()
        v.backgroundColor = .systemBackground
        v.layer.cornerRadius = 16
        v.layer.borderWidth = 1
        v.layer.borderColor = UIColor.systemGray4.cgColor
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()
    
    private let iconView: UIView = {
        let v = UIView()
        v.backgroundColor = .systemBlue.withAlphaComponent(0.1)
        v.layer.cornerRadius = 20
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()
    
    private let iconLabel: UILabel = {
        let label = UILabel()
        label.text = "📊"
        label.font = .systemFont(ofSize: 20)
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()
    
    private let questionLabel: UILabel = {
        let label = UILabel()
        label.text = "Ok, what are we thinking for types of cuisine?"
        label.font = .systemFont(ofSize: 15, weight: .semibold)
        label.numberOfLines = 0
        label.textColor = .label
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()
    
    private let optionsStackView: UIStackView = {
        let sv = UIStackView()
        sv.axis = .vertical
        sv.spacing = 8
        sv.translatesAutoresizingMaskIntoConstraints = false
        return sv
    }()
    
    // MARK: - Init
    override init(frame: CGRect) {
        super.init(frame: frame)
        setupUI()
        createOptionButtons()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    // MARK: - Setup
    private func setupUI() {
        translatesAutoresizingMaskIntoConstraints = false
        
        addSubview(containerView)
        containerView.addSubview(iconView)
        iconView.addSubview(iconLabel)
        containerView.addSubview(questionLabel)
        containerView.addSubview(optionsStackView)
        
        NSLayoutConstraint.activate([
            containerView.topAnchor.constraint(equalTo: topAnchor),
            containerView.leadingAnchor.constraint(equalTo: leadingAnchor),
            containerView.trailingAnchor.constraint(equalTo: trailingAnchor),
            containerView.bottomAnchor.constraint(equalTo: bottomAnchor),
            
            iconView.topAnchor.constraint(equalTo: containerView.topAnchor, constant: 12),
            iconView.leadingAnchor.constraint(equalTo: containerView.leadingAnchor, constant: 12),
            iconView.widthAnchor.constraint(equalToConstant: 40),
            iconView.heightAnchor.constraint(equalToConstant: 40),
            
            iconLabel.centerXAnchor.constraint(equalTo: iconView.centerXAnchor),
            iconLabel.centerYAnchor.constraint(equalTo: iconView.centerYAnchor),
            
            questionLabel.topAnchor.constraint(equalTo: containerView.topAnchor, constant: 16),
            questionLabel.leadingAnchor.constraint(equalTo: iconView.trailingAnchor, constant: 12),
            questionLabel.trailingAnchor.constraint(equalTo: containerView.trailingAnchor, constant: -12),
            
            optionsStackView.topAnchor.constraint(equalTo: questionLabel.bottomAnchor, constant: 12),
            optionsStackView.leadingAnchor.constraint(equalTo: containerView.leadingAnchor, constant: 12),
            optionsStackView.trailingAnchor.constraint(equalTo: containerView.trailingAnchor, constant: -12),
            optionsStackView.bottomAnchor.constraint(equalTo: containerView.bottomAnchor, constant: -12)
        ])
    }
    
    private func createOptionButtons() {
        for option in pollOptions {
            let button = createOptionButton(text: option)
            optionsStackView.addArrangedSubview(button)
        }
    }
    
    private func createOptionButton(text: String) -> UIButton {
        let button = UIButton(type: .system)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.heightAnchor.constraint(equalToConstant: 44).isActive = true
        
        button.backgroundColor = .systemGray6
        button.layer.cornerRadius = 10
        button.layer.borderWidth = 1.5
        button.layer.borderColor = UIColor.clear.cgColor
        
        button.setTitle(text, for: .normal)
        button.setTitleColor(.label, for: .normal)
        button.titleLabel?.font = .systemFont(ofSize: 16, weight: .medium)
        button.contentHorizontalAlignment = .leading
        button.contentEdgeInsets = UIEdgeInsets(top: 0, left: 12, bottom: 0, right: 12)
        
        // No interaction - just display
        button.isUserInteractionEnabled = false
        
        return button
    }
}

// MARK: - Poll Cell for TableView
class PollMessageCell: UITableViewCell {
    
    private let pollView = EmbeddedPollView()
    
    override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
        super.init(style: style, reuseIdentifier: reuseIdentifier)
        setupUI()
    }
    
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
    
    private func setupUI() {
        backgroundColor = .clear
        selectionStyle = .none
        
        contentView.addSubview(pollView)
        
        NSLayoutConstraint.activate([
            pollView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 8),
            pollView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
            pollView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -12),
            pollView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -8)
        ])
    }
}
